import argparse
import sys
import libvirt
import xml.etree.ElementTree as ET

# Helper functions for VM operations
def get_vm_ip(vm_name, network_name='default'):
    try:
        conn = libvirt.open("qemu:///system")
    except libvirt.libvirtError as e:
        return f"Libvirt error: {str(e)}"
    domain = conn.lookupByName(vm_name)
    xml_desc = domain.XMLDesc()
    root = ET.fromstring(xml_desc)
    macs = [iface.get('address').lower() for iface in root.findall("./devices/interface/mac") if iface.get('address')]
    if not macs:
        return None
    network = conn.networkLookupByName(network_name)
    leases = network.DHCPLeases()
    for lease in leases:
        if lease['mac'].lower() in macs:
            return lease['ipaddr']
    return None

def shutdown_vm(vm_name):
    try:
        conn = libvirt.open("qemu:///system")
    except libvirt.libvirtError as e:
        return f"Libvirt error: {str(e)}"
    try:
        domain = conn.lookupByName(vm_name)
        if domain.isActive():
            domain.shutdown()
        conn.close()
        return "OK"
    except libvirt.libvirtError as e:
        return f"Libvirt error: {str(e)}"

def destroy_vm(vm_name):
    try:
        conn = libvirt.open("qemu:///system")
    except libvirt.libvirtError as e:
        return f"Libvirt error: {str(e)}"
    try:
        domain = conn.lookupByName(vm_name)
        if domain.isActive():
            domain.destroy()
        domain.undefine()
        conn.close()
        return "OK"
    except libvirt.libvirtError as e:
        return f"Libvirt error: {str(e)}"

def list_vms():
    try:
        conn = libvirt.open("qemu:///system")
    except libvirt.libvirtError as e:
        return f"Libvirt error: {str(e)}"
    vms = {}
    for dom in conn.listAllDomains():
        name = dom.name()
        is_active = dom.isActive()
        vms[name] = {
            'id': dom.ID() if is_active else None,
            'active': is_active,
            'uuid': dom.UUIDString()
        }
    conn.close()
    return vms

def create_vm(name, cores, memory, path):
    try:
        conn = libvirt.open("qemu:///system")
    except libvirt.libvirtError as e:
        return f"Libvirt error: {str(e)}"
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
        <console type='pty' tty='/dev/pts/2'>
        </console>
        <interface type='network'>
        <mac address='52:54:00:0c:94:61'/>
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
    domain.create()
    conn.close()
    return "OK"

def create_vm_snapshot(vm_name, snapshot_name, description=""):
    try:
        conn = libvirt.open("qemu:///system")
    except libvirt.libvirtError as e:
        return f"Libvirt error: {str(e)}"
    try:
        domain = conn.lookupByName(vm_name)
        snapshot_xml = f"""
        <domainsnapshot>
            <name>{snapshot_name}</name>
            <description>{description}</description>
        </domainsnapshot>
        """
        domain.snapshotCreateXML(snapshot_xml, 0)
        conn.close()
        return "OK"
    except libvirt.libvirtError as e:
        return f"Libvirt error: {str(e)}"

def list_vm_snapshots(vm_name):
    try:
        conn = libvirt.open("qemu:///system")
    except libvirt.libvirtError as e:
        return f"Libvirt error: {str(e)}"
    try:
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
        conn.close()
        return snapshots
    except libvirt.libvirtError as e:
        return f"Libvirt error: {str(e)}"

def revert_vm_snapshot(vm_name, snapshot_name):
    try:
        conn = libvirt.open("qemu:///system")
    except libvirt.libvirtError as e:
        return f"Libvirt error: {str(e)}"
    try:
        domain = conn.lookupByName(vm_name)
        snapshot = domain.snapshotLookupByName(snapshot_name, 0)
        domain.revertToSnapshot(snapshot, 0)
        conn.close()
        return "OK"
    except libvirt.libvirtError as e:
        return f"Libvirt error: {str(e)}"

def start_vm(vm_name):
    try:
        conn = libvirt.open("qemu:///system")
    except libvirt.libvirtError as e:
        return f"Libvirt error: {str(e)}"
    try:
        domain = conn.lookupByName(vm_name)
        domain.create()
        conn.close()
        return "OK"
    except libvirt.libvirtError as e:
        return f"Libvirt error: {str(e)}"

def reboot_vm(vm_name):
    try:
        conn = libvirt.open("qemu:///system")
    except libvirt.libvirtError as e:
        return f"Libvirt error: {str(e)}"
    try:
        domain = conn.lookupByName(vm_name)
        domain.reboot(0)
        conn.close()
        return "OK"
    except libvirt.libvirtError as e:
        return f"Libvirt error: {str(e)}"

# CLI argument parsing
def main():
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
