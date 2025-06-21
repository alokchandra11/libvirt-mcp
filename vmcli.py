#!/usr/bin/env python3
import libvirt
import xml.etree.ElementTree as ET
import random
from typing import Union, Dict, Any, List

def get_vm_ip(vm_name: str, network_name: str = 'default') -> Union[str, None]:
    """
    Get the IP address of a Virtual Machine.
    Returns the IP address as a string, an error message string, or None if not found.
    """
    conn = None
    try:
        conn = libvirt.open("qemu:///system")
        try:
            domain = conn.lookupByName(vm_name)
        except libvirt.libvirtError as e:
            return f"Libvirt error: {str(e)}"
        xml_desc = domain.XMLDesc()
        root = ET.fromstring(xml_desc)
        macs = []
        for iface in root.findall("./devices/interface/mac"):
            addr = iface.get('address')
            if addr is not None:
                macs.append(addr.lower())
        if not macs:
            return None
        try:
            network = conn.networkLookupByName(network_name)
            leases = network.DHCPLeases()
        except libvirt.libvirtError as e:
            return f"Libvirt error: {str(e)}"
        for lease in leases:
            if lease['mac'].lower() in macs:
                return lease['ipaddr']
        return None
    except libvirt.libvirtError as e:
        return f"Libvirt error: {str(e)}"
    finally:
        if conn:
            conn.close()

def shutdown_vm(vm_name: str) -> str:
    """
    Shutdown a virtual machine by name.
    """
    conn = None
    try:
        conn = libvirt.open("qemu:///system")
        domain = conn.lookupByName(vm_name)
        if domain.isActive():
            domain.shutdown()
        return "OK"
    except libvirt.libvirtError as e:
        return f"Libvirt error: {str(e)}"
    finally:
        if conn:
            conn.close()

def destroy_vm(vm_name: str) -> str:
    """
    Destroy and undefine a virtual machine by name.
    """
    conn = None
    try:
        conn = libvirt.open("qemu:///system")
        domain = conn.lookupByName(vm_name)
        if domain.isActive():
            domain.destroy()
        domain.undefine()
        return "OK"
    except libvirt.libvirtError as e:
        return f"Libvirt error: {str(e)}"
    finally:
        if conn:
            conn.close()

def list_vms() -> Union[Dict[str, Any], str]:
    """
    List all virtual machines.
    """
    conn = None
    try:
        conn = libvirt.open("qemu:///system")
        vms = {}
        for dom in conn.listAllDomains():
            name = dom.name()
            is_active = dom.isActive()
            vms[name] = {
                'id': dom.ID() if is_active else None,
                'active': is_active,
                'uuid': dom.UUIDString()
            }
        return vms
    except libvirt.libvirtError as e:
        return f"Libvirt error: {str(e)}"
    finally:
        if conn:
            conn.close()

def generate_mac() -> str:
    mac = [0x52, 0x54, 0x00,
           random.randint(0x00, 0x7f),
           random.randint(0x00, 0xff),
           random.randint(0x00, 0xff)]
    return ':'.join(map(lambda x: "%02x" % x, mac))

def create_vm(name: str, cores: int, memory: int, path: str) -> str:
    """
    Create a new virtual machine.
    """
    # Input validation
    if not isinstance(cores, int) or cores < 1:
        return "Invalid number of CPU cores."
    if not isinstance(memory, int) or memory < 128:
        return "Invalid memory size. Must be at least 128 MiB."
    if not name or not isinstance(name, str) or any(c in name for c in "<>&'\""):
        return "Invalid VM name."
    if not path or not isinstance(path, str) or any(c in path for c in "<>&'\""):
        return "Invalid disk image path."
    conn = None
    try:
        conn = libvirt.open("qemu:///system")
        # Check if VM already exists
        try:
            if conn.lookupByName(name):
                return f"VM '{name}' already exists."
        except libvirt.libvirtError:
            pass  # Not found, OK
        mac_addr = generate_mac()
        domain_xml = f"""
        <domain type='kvm'>
          <name>{name}</name>
          <memory unit='MiB'>{memory}</memory>
          <vcpu>{cores}</vcpu>
          <os>
            <type arch='x86_64'>hvm</type>
            <boot dev='hd'/>
          </os>
          <devices>
            <disk type='file' device='disk'>
              <driver name='qemu' type='qcow2'/>
              <source file='{path}'/>
              <target dev='vda' bus='virtio'/>
            </disk>
            <console type='pty'/>
            <interface type='network'>
              <mac address='{mac_addr}'/>
              <source network='default'/>
              <model type='virtio'/>
            </interface>
          </devices>
        </domain>
        """
        try:
            domain = conn.defineXML(domain_xml)
        except libvirt.libvirtError as e:
            return f"Libvirt error: {str(e)}"
        if domain is None:
            return "Failed to define the domain."
        try:
            domain.create()
        except libvirt.libvirtError as e:
            return f"Libvirt error (create): {str(e)}"
        return "OK"
    except libvirt.libvirtError as e:
        return f"Libvirt error: {str(e)}"
    finally:
        if conn:
            conn.close()

def create_vm_snapshot(vm_name: str, snapshot_name: str, description: str = "") -> str:
    """
    Create a snapshot for a virtual machine.
    """
    conn = None
    try:
        conn = libvirt.open("qemu:///system")
        domain = conn.lookupByName(vm_name)
        snapshot_xml = f"""
        <domainsnapshot>
            <name>{snapshot_name}</name>
            <description>{description}</description>
        </domainsnapshot>
        """
        domain.snapshotCreateXML(snapshot_xml, 0)
        return "OK"
    except libvirt.libvirtError as e:
        return f"Libvirt error: {str(e)}"
    finally:
        if conn:
            conn.close()

def list_vm_snapshots(vm_name: str) -> Union[List[Dict[str, Any]], str]:
    """
    List all snapshots for a virtual machine.
    """
    conn = None
    try:
        conn = libvirt.open("qemu:///system")
        domain = conn.lookupByName(vm_name)
        snapshot_names = domain.snapshotListNames(0)
        snapshots = []
        for snap_name in snapshot_names:
            snap = domain.snapshotLookupByName(snap_name, 0)
            snap_xml = snap.getXMLDesc(0)
            root = ET.fromstring(snap_xml)
            creation_time = root.findtext('creationTime')
            state = root.findtext('state')
            snapshots.append({
                'name': snap_name,
                'creation_time': creation_time,
                'state': state
            })
        return snapshots
    except libvirt.libvirtError as e:
        return f"Libvirt error: {str(e)}"
    finally:
        if conn:
            conn.close()

def revert_vm_snapshot(vm_name: str, snapshot_name: str) -> str:
    """
    Revert a virtual machine to a specified snapshot.
    """
    conn = None
    try:
        conn = libvirt.open("qemu:///system")
        domain = conn.lookupByName(vm_name)
        snapshot = domain.snapshotLookupByName(snapshot_name, 0)
        domain.revertToSnapshot(snapshot, 0)
        return "OK"
    except libvirt.libvirtError as e:
        return f"Libvirt error: {str(e)}"
    finally:
        if conn:
            conn.close()

def start_vm(vm_name: str) -> str:
    """
    Start a virtual machine by name.
    """
    conn = None
    try:
        conn = libvirt.open("qemu:///system")
        domain = conn.lookupByName(vm_name)
        domain.create()
        return "OK"
    except libvirt.libvirtError as e:
        return f"Libvirt error: {str(e)}"
    finally:
        if conn:
            conn.close()

def reboot_vm(vm_name: str) -> str:
    """
    Reboot a virtual machine by name.
    """
    conn = None
    try:
        conn = libvirt.open("qemu:///system")
        domain = conn.lookupByName(vm_name)
        domain.reboot(0)
        return "OK"
    except libvirt.libvirtError as e:
        return f"Libvirt error: {str(e)}"
    finally:
        if conn:
            conn.close()

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Libvirt VM CLI Tool")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("list-vms", help="List all VMs")

    parser_create = subparsers.add_parser("create-vm", help="Create a new VM")
    parser_create.add_argument("name")
    parser_create.add_argument("cores", type=int)
    parser_create.add_argument("memory", type=int)
    parser_create.add_argument("path")

    parser_start = subparsers.add_parser("start-vm", help="Start a VM")
    parser_start.add_argument("name")

    parser_shutdown = subparsers.add_parser("shutdown-vm", help="Shutdown a VM")
    parser_shutdown.add_argument("name")

    parser_destroy = subparsers.add_parser("destroy-vm", help="Destroy a VM")
    parser_destroy.add_argument("name")

    parser_ip = subparsers.add_parser("get-vm-ip", help="Get VM IP")
    parser_ip.add_argument("name")
    parser_ip.add_argument("--network", default="default")

    parser_snapshot = subparsers.add_parser("create-vm-snapshot", help="Create VM snapshot")
    parser_snapshot.add_argument("name")
    parser_snapshot.add_argument("snapshot")
    parser_snapshot.add_argument("--description", default="")

    parser_list_snap = subparsers.add_parser("list-vm-snapshots", help="List VM snapshots")
    parser_list_snap.add_argument("name")

    parser_revert_snap = subparsers.add_parser("revert-vm-snapshot", help="Revert VM to snapshot")
    parser_revert_snap.add_argument("name")
    parser_revert_snap.add_argument("snapshot")

    parser_reboot = subparsers.add_parser("reboot-vm", help="Reboot a VM")
    parser_reboot.add_argument("name")

    args = parser.parse_args()
    if args.command == "list-vms":
        print(list_vms())
    elif args.command == "create-vm":
        print(create_vm(args.name, args.cores, args.memory, args.path))
    elif args.command == "start-vm":
        print(start_vm(args.name))
    elif args.command == "shutdown-vm":
        print(shutdown_vm(args.name))
    elif args.command == "destroy-vm":
        print(destroy_vm(args.name))
    elif args.command == "get-vm-ip":
        print(get_vm_ip(args.name, args.network))
    elif args.command == "create-vm-snapshot":
        print(create_vm_snapshot(args.name, args.snapshot, args.description))
    elif args.command == "list-vm-snapshots":
        print(list_vm_snapshots(args.name))
    elif args.command == "revert-vm-snapshot":
        print(revert_vm_snapshot(args.name, args.snapshot))
    elif args.command == "reboot-vm":
        print(reboot_vm(args.name))
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
