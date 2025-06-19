import libvirt
import xml.etree.ElementTree as ET

def register_handlers(mcp):

    # List available resources
    @mcp.resource("list://resources")
    def list_resources() -> dict:
        """Return a list of all available resources in this server."""
        return {
            "resources": [
                {
                    "uri": "images://{os_name}",
                    "name": "Operating System Images",
                    "description": "Return the path to an image in the system with the Distribution installed",
                    "mime_type": "text/plain",
                }
            ]
        }

    # Define a resource template with a parameter
    @mcp.resource("images://{os_name}")
    def get_os_image_path(os_name: str) -> str:
        """Return the path in the system to a disk with OS installed"""
        return f"/var/lib/libvirt/images/{os_name}.qcow2"

    @mcp.tool()
    def get_vm_ip(vm_name, network_name='default'):
        """
        Get IP of a Virtual Machine given its name.

        Args:
          vm_name: Virtual Machine name.

        Returns:
           IP if successes, `Error` otherwise.
        """
        try:
            conn = libvirt.open("qemu:///system")
        except libvirt.libvirtError as e:
            return f"Libvirt error: {str(e)}"

        domain = conn.lookupByName(vm_name)

        xml_desc = domain.XMLDesc()
        root = ET.fromstring(xml_desc)

        macs = []
        for iface in root.findall("./devices/interface/mac"):
            mac = iface.get('address')
            if mac:
                macs.append(mac.lower())

        if not macs:
            return None

        network = conn.networkLookupByName(network_name)
        leases = network.DHCPLeases()

        for lease in leases:
            if lease['mac'].lower() in macs:
                return lease['ipaddr']

        return None

    @mcp.tool()
    def shutdown_vm(vm_name: str):
        """
        Shutdown the execution of an existing Virtual Machine(VM) given its name.
        The VM may ignore the request.

        Args:
          vm_name: Virtual Machine name.

        Returns:
           `OK` if successes, `Error` otherwise.
        """
        try:
            conn = libvirt.open("qemu:///system")
        except libvirt.libvirtError as e:
            return f"Libvirt error: {str(e)}"

        try:
            domain = conn.lookupByName(vm_name)

            if domain.isActive():
                domain.shutdown()

            return "OK"
        except libvirt.libvirtError as e:
            print(f"Error: {e}")

        conn.close()

    @mcp.tool()
    def destroy_vm(vm_name: str):
        """
        Destroy an existing Virtual Machine(VM) given its name. This method
        destroys and undefines the VM.

        Args:
          vm_name: Virtual Machine name.

        Returns:
           `OK` if successes, `Error` otherwise.
        """
        try:
            conn = libvirt.open("qemu:///system")
        except libvirt.libvirtError as e:
            return f"Libvirt error: {str(e)}"

        try:
            domain = conn.lookupByName(vm_name)

            if domain.isActive():
                domain.destroy()

            domain.undefine()

            return "OK"
        except libvirt.libvirtError as e:
            print(f"Error: {e}")

        conn.close()

    @mcp.tool()
    def list_vms():
        """
        Returns a list of Virtual Machines (VMs) both running or defined in current system

        Args:

        Returns:
          A dictionary in which each entry is the name of the VM and then
          the first column is the id, the second column is the status and the third
          column is the uuid.
        """
        try:
            conn = libvirt.open("qemu:///system")
        except libvirt.libvirtError as e:
            return f"Libvirt error: {str(e)}"

        vms = {}

        # Get all domains (both active and inactive)
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

    @mcp.tool()
    def create_vm(name: str, cores: int, memory: int, path: str) -> str:
        """
        Create a Virtual Machine (VM) with a given name and with a given number of
        cores and a given amount of memory and using a image in path.

        Args:
          name: name of the virtual machine
          cores: number of cores
          memory: amount of memory in megabytes
          path: path to the image for the disk

        Returns:
          `OK` if success, `Error` otherwise
        """
        try:
            conn = libvirt.open("qemu:///system")
        except libvirt.libvirtError as e:
            return f"Libvirt error: {str(e)}"

        # XML definition of the VM
        # set parameters from arguments
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

        # TODO: to check if this fails, e.g., VM already exists
        domain.create()
        conn.close()
        return "OK"

    @mcp.tool()
    def create_vm_snapshot(vm_name: str, snapshot_name: str, description: str = ""):
        """
        Create a snapshot for a Virtual Machine (VM) given its name and snapshot name.

        Args:
          vm_name: Name of the virtual machine
          snapshot_name: Name for the snapshot
          description: Optional description for the snapshot

        Returns:
          'OK' if success, error message otherwise
        """
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

    @mcp.tool()
    def list_vm_snapshots(vm_name: str):
        """
        List all snapshots for a given Virtual Machine (VM), equivalent to 'virsh snapshot-list'.

        Args:
          vm_name: Name of the virtual machine

        Returns:
          A list of dictionaries with snapshot details (name, creation time, state), or error message.
        """
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

    @mcp.tool()
    def revert_vm_snapshot(vm_name: str, snapshot_name: str):
        """
        Revert a Virtual Machine (VM) to a specified snapshot, equivalent to 'virsh snapshot-revert'.

        Args:
          vm_name: Name of the virtual machine
          snapshot_name: Name of the snapshot to revert to

        Returns:
          'OK' if success, error message otherwise
        """
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

    @mcp.tool()
    def start_vm(vm_name: str):
        """
        Start a Virtual Machine (VM) given its name, equivalent to 'virsh start'.

        Args:
          vm_name: Name of the virtual machine

        Returns:
          'OK' if success, error message otherwise
        """
        try:
            conn = libvirt.open("qemu:///system")
        except libvirt.libvirtError as e:
            return f"Libvirt error: {str(e)}"

        try:
            domain = conn.lookupByName(vm_name)
            domain.create()  # This starts the VM
            conn.close()
            return "OK"
        except libvirt.libvirtError as e:
            return f"Libvirt error: {str(e)}"

    @mcp.tool()
    def reboot_vm(vm_name: str):
        """
        Reboot a Virtual Machine (VM) given its name, equivalent to 'virsh reboot'.

        Args:
          vm_name: Name of the virtual machine

        Returns:
          'OK' if success, error message otherwise
        """
        try:
            conn = libvirt.open("qemu:///system")
        except libvirt.libvirtError as e:
            return f"Libvirt error: {str(e)}"

        try:
            domain = conn.lookupByName(vm_name)
            domain.reboot(0)  # 0 means default reboot flags
            conn.close()
            return "OK"
        except libvirt.libvirtError as e:
            return f"Libvirt error: {str(e)}"


