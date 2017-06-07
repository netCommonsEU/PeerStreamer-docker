import argparse
import argparse_actions
import serf
import sys
import base64
import bz2
from pyroute2 import IPRoute
import portalocker
import time


class PsngSerfClient:

    def __init__(self, tag_name, rpc_address, rpc_port):
        self.tag_name = tag_name
        self.rpc_address = rpc_address
        self.rpc_port = rpc_port
        self.ch_dbfile = None
        self.client = None
        # Remember all tags parsed the last time
        self.last_channels_tags_list = []

    def encode_and_compress(self, s):
        ret_data = base64.b64encode(s)
        ret_data = bz2.compress(ret_data)

        return ret_data

    def decompress_and_decode(self, data):
        ret_str = bz2.decompress(data)
        ret_str = base64.b64decode(ret_str)

        return ret_str

    def encode(self, s):
        ret_data = base64.b64encode(s)

        return ret_data

    def decode(self, data):
        ret_str = base64.b64decode(data)

        return ret_str

    def get_local_ips(self):
        ip = IPRoute()
        local_if = ip.get_addr()
        local_ips = []
        for interf in local_if:
            local_ips.append(interf.get_attr('IFA_ADDRESS'))

        return local_ips

    def get_members(self):
        # Retrieve informations from all the serf memebrs.
        # This is done through the RPC members call.

        resp = None

        try:
            client = serf.Client("%s:%d" % (self.rpc_address, self.rpc_port))
            client.connect()
            client.members()
            resp = client.request(timeout=5)
            client.disconnect()
        except serf._exceptions.ConnectionError:
            print "Connection error"

        return resp

    def set_tag(self, tag_dict):
        resp = None

        try:
            client = serf.Client("%s:%d" % (self.rpc_address, self.rpc_port))
            client.connect()
            client.tags(Tags=tag_dict)
            resp = client.request()
            client.disconnect()
        except serf._exceptions.ConnectionError:
            print "Connection error"

        return resp

    def del_tag(self, tag_names_list):
        resp = None

        try:
            client = serf.Client("%s:%d" % (self.rpc_address, self.rpc_port))
            client.connect()
            client.tags(DeleteTags=tag_names_list)
            resp = client.request()
            client.disconnect()
        except serf._exceptions.ConnectionError:
            print "Connection error"

        return resp

    def is_local_member(self, member, local_ips):
        if member["Addr"]:
            m_addr = ".".join([str(x) for x in member["Addr"]])
            if m_addr in local_ips:
                return True
            else:
                return False
        else:
            print "Warning: found a memeber without address\n"
            print member
            return False

    def write_db_file(self, file_name, channels_list):

        file_hdr = "# channel_name,source_addr,source_port,channel_params"

        db_file = open(file_name, 'w')
        portalocker.lock(db_file, portalocker.LOCK_EX)
        db_file.write("%s\n" % (file_hdr,))
        for c in channels_list:
            print "Add channel: %s" % (c,)
            db_file.write("%s\n" % (c,))

        db_file.close()

    def member_update_event_callback(self, resp):

        if resp.is_success:
            print "Received event: member-update"
            resp_body = resp.body
            members = resp_body["Members"]

            for m in members:
                # For now we consider only "alive" members
                if m["Status"] == "alive":
                    if m["Tags"]:
                        if m["Tags"].get(self.tag_name):
                            c_tag = m["Tags"].get(self.tag_name)
                            if c_tag not in self.last_channels_tags_list:
                                self.update_db_from_members()
                                return 0
        else:
            sys.stderr.write("Serf streamed event failed\n")
            sys.stderr.write("%s" % (resp.error,))

        return 0

    def listen_for_member_update_events(self, ch_dbfile):
        print "Database file: %s" % (ch_dbfile,)

        while True:

            # Write the db file based on the current members channels tags
            members_updated = False
            sleep_time = 5

            self.client = serf.Client("%s:%d" % (self.rpc_address,
                                      self.rpc_port),
                                      auto_reconnect=True)

            while not members_updated:
                try:
                    self.client.connect()

                    self.ch_dbfile = ch_dbfile
                    if self.update_db_from_members():
                        members_updated = True
                    else:
                        time.sleep(sleep_time)
                except serf._exceptions.ConnectionError:
                    print "Client connection error (sleep %d)" % (sleep_time,)
                    time.sleep(sleep_time)

            try:
                # Register callback for memebr update events
                # Todo: handle sigint
                self.client.stream(Type="member-update").add_callback(
                                   self.member_update_event_callback).request(
                                   timeout=120)
            except serf._exceptions.ConnectionError:
                print "Client connection error (sleep %d)" % (sleep_time,)
                time.sleep(sleep_time)
            except KeyboardInterrupt:
                print "Disconnection from RPC deamon"
                self.client.disconnect()
                return

    def update_db_from_members(self):
        # WARNING: This method assumes the connection towards the RPC deamon
        # is already open and the client seved in self.client

        if not self.client:
            return False

        # Retrieve serf members
        self.client.members()
        resp = self.client.request(timeout=5)

        if resp[0].is_success:
            resp_body = resp[0].body
            members = resp_body["Members"]

            # Retrieve channel tags
            self.last_channels_tags_list = []
            channel_tags_list = []

            for m in members:
                # For now we consider only "alive" members
                if m["Status"] == "alive":
                    if m["Tags"]:
                        if m["Tags"].get(self.tag_name):
                            c_tag = m["Tags"].get(self.tag_name)
                            channel_tags_list.append(c_tag)
                            self.last_channels_tags_list.append(c_tag)

            # Build channels list
            channels_list = []

            for t_comp in channel_tags_list:
                # Decode the channel tag
                t = self.decode(t_comp)

                # Each member can have more than one channel.
                # Channels are separated by the ";" character.
                channels_list += t.split(";")

            # Write database file
            self.write_db_file(self.ch_dbfile, channels_list)

            return True

        else:
            self.write_db_file(self.ch_dbfile, [])
            sys.stderr.write("Serf members command failed\n")
            sys.stderr.write("%s" % (resp[0].error,))
            return False

    def delete_channel(self, ch_addr, ch_port):
        resp = self.get_members()

        if not resp:
            return

        if resp[0].is_success:
            resp_body = resp[0].body
            members = resp_body["Members"]

            # Used to save the channels tag of the local memebr
            local_node_channels = None
            channels_tag_exist = False
            new_channels_string = ""
            delete_channel = False

            # find all local IP addresses and save them in local_ips
            local_ips = self.get_local_ips()

            for m in members:
                # For now we consider only "alive" members
                if m["Status"] == "alive":
                    if self.is_local_member(m, local_ips):
                        if m["Tags"]:
                            if m["Tags"].get(self.tag_name):
                                channels_tag_exist = True
                            local_node_channels = m["Tags"].get(self.tag_name)

            if local_node_channels:
                # Decompress and decode the local channel and compare to the
                # channel we want to delete
                # The channel are compared only considering the
                # address and the port
                channels = self.decode(local_node_channels)

                # Each member can have more than one channel.
                # Channels are separated by the ";" character.
                channels_list = channels.split(";")

                for c in channels_list:
                    [_, caddr, cport, _] = c.split(",")

                    if (caddr != ch_addr or int(cport) != int(ch_port)):
                        # This is not the channel we want to delete.
                        # Add it to the new channels string
                        if new_channels_string:
                            new_channels_string += ";" + c
                        else:
                            new_channels_string = c
                    else:
                        delete_channel = True
                        print "Delete channel: %s" % (c,)

            if new_channels_string and delete_channel:
                # If new_channels_string is not empty we just need to update
                # the channels tag through the RPC tags -set call.

                print "Update channels: %s" % (new_channels_string,)

                # Encode the string
                ch_str_comp = self.encode(new_channels_string)

                # Update (or add) the channels tag.
                # This is done through the RCP tags call

                resp = self.set_tag({self.tag_name: ch_str_comp})

                if not resp:
                    return

                if not resp[0].is_success:
                    sys.stderr.write("Serf tags set command failed\n")
                    sys.stderr.write("%s" % (resp[0].error,))

            elif not new_channels_string and channels_tag_exist:
                # If new_channels_string is empty but channels_tag_exist
                # is True we can delete che cahnnels tag through the RPC
                # tags -delete call
                print "Delete tag: %s" % (self.tag_name,)

                resp = self.del_tag((self.tag_name,))

                if not resp:
                    return

                if not resp[0].is_success:
                    sys.stderr.write("Serf tags delete command failed\n")
                    sys.stderr.write("%s" % (resp[0].error,))

        else:
            sys.stderr.write("Serf members command failed\n")
            sys.stderr.write("%s" % (resp[0].error,))
            return

    def set_new_channel(self, ch_addr, ch_port, ch_name, ch_txt):
        # Build new channel string
        ch_str = '%s,%s,%d,%s' % (ch_name, ch_addr, ch_port, ch_txt)
        print "Add channel: %s\n" % (ch_str,)

        # Retrieve informations from all the serf memebrs.
        resp = self.get_members()

        if not resp:
            return

        if resp[0].is_success:
            resp_body = resp[0].body
            members = resp_body["Members"]

            # One encoded channels string for each "alive" member
            nodes_channels_list = []
            # Used to save the channels tag of the local memebr
            local_node_channels = None

            # find all local IP addresses and save them in local_ips
            local_ips = self.get_local_ips()

            for m in members:
                # For now we consider only "alive" members
                if m["Status"] == "alive":

                    # Check if this is the local member
                    local_member = self.is_local_member(m, local_ips)

                    # Save the channels tag
                    if m["Tags"]:
                        node_channels = m["Tags"].get(self.tag_name)

                        if node_channels:
                            nodes_channels_list.append(node_channels)
                            if local_member:
                                local_node_channels = node_channels

            # Don't add the new channel if it already exists
            for channels_comp in nodes_channels_list:
                # Dont' consider empty strings
                if not channels_comp:
                    continue

                # Decompress and decode each channel and compare to the new
                # channel we want to set
                # The channel are compared only considering the
                # address and the port
                channels = self.decode(channels_comp)

                # Each member can have more than one channel.
                # Channels are separated by the ";" character.
                channels_list = channels.split(";")

                for c in channels_list:
                    [_, caddr, cport, _] = c.split(",")

                    if (caddr == ch_addr and int(cport) == int(ch_port)):
                        print "Channel already exists"
                        return

            # If we arrive here this means that we are trying to add a new
            # channel.
            # Encode and compress data
            if local_node_channels:
                ch_str = ';'.join([self.decode(
                                  local_node_channels),
                                  ch_str])
            ch_str_comp = self.encode(ch_str)

            # Update (or add) the channels tag.
            # This is done through the RCP tags call
            resp = self.set_tag({self.tag_name: ch_str_comp})

            if not resp:
                return

            if not resp[0].is_success:
                sys.stderr.write("Serf tags command failed\n")
                sys.stderr.write("%s" % (resp[0].error,))

        else:
            sys.stderr.write("Serf members command failed\n")
            sys.stderr.write("%s" % (resp[0].error,))
            return

    def __str__(self):
        ret_str = "PSNG Serf RPC client: "
        ret_str += "{channels_tag_name: %s, " % (self.tag_name,)
        ret_str += "rpc_address: %s, " % (self.rpc_address,)
        ret_str += "rpc_port %d}\n" % (self.rpc_port,)
        return ret_str


def psng_serf_client_init():
    parser = argparse.ArgumentParser()

    # Optionals
    parser.add_argument("-t", "--tagname", type=str, default="psngc",
                        help="PeerStreamer Next-Generation source tag name",
                        dest="tagname")

    # Mandatory for all modes
    parser.add_argument("-a", "--rpcaddress", type=str, required=True,
                        help="IP address of the Serf RPC server",
                        dest="rpcaddress",
                        action=argparse_actions.ProperIpFormatAction)
    parser.add_argument("-p", "--rpcport", type=int, required=True,
                        help="TCP port of the Serf RPC server",
                        dest="rpcport", choices=range(0, 65536),
                        metavar="[0-65535]")

    subparsers = parser.add_subparsers(dest="command")
    # Set PeerStreamer Next-Generation source tag
    parser_set = subparsers.add_parser("set", help="Set and propagate the "
                                       "PeerStreamer Next-Generation "
                                       "source tag (Call RPC tags --set). "
                                       "If this node has already a "
                                       "PeerStreamer Next-Generation source "
                                       "tag associated, then the new channel "
                                       "is appended to the existing ones.")
    parser_set.add_argument("caddr", type=str,
                            help="Source channel IP address",
                            action=argparse_actions.ProperIpFormatAction)
    parser_set.add_argument("cport", type=int, choices=range(0, 65536),
                            help="Source channel port",
                            metavar="[0-65535]")
    parser_set.add_argument("cname", type=str,
                            help="Source channel name")
    parser_set.add_argument("ctxt", type=str,
                            help="Source channel additional parameters")

    # Delete PeerStreamer Next-Generation source tag
    parser_del = subparsers.add_parser("del", help="Delete a channel "
                                       "identified by a source address, a "
                                       "source port and a name. If the "
                                       "resulting PeerStreamer "
                                       "Next-Generation source tag is empty, "
                                       "then it will be deleted by calling "
                                       "the RPC procedure tags --delete.")
    parser_del.add_argument("caddr", type=str,
                            help="Source channel IP address",
                            action=argparse_actions.ProperIpFormatAction)
    parser_del.add_argument("cport", type=int, choices=range(0, 65536),
                            help="Source channel port",
                            metavar="[0-65535]")
    # parser_del.add_argument("cname", type=str,
    #                         help="Source channel name")

    parser_db = subparsers.add_parser("bg",
                                      help="Run in background and keep the "
                                      "database file updated by listening to "
                                      "member-update Serf events.")
    parser_db.add_argument("dbfile", type=str,
                           help="Channels database file")

    try:
        args = parser.parse_args()

        tag_name = args.tagname
        rpc_address = args.rpcaddress
        rpc_port = args.rpcport

        serf_client = PsngSerfClient(tag_name, rpc_address, rpc_port)
        print(serf_client)

        command = args.command
        if command == "bg":
            ch_dbfile = args.dbfile
            serf_client.listen_for_member_update_events(ch_dbfile)
        elif command == "set":
            ch_addr = args.caddr
            ch_port = args.cport
            ch_name = args.cname
            ch_txt = args.ctxt
            serf_client.set_new_channel(ch_addr, ch_port, ch_name, ch_txt)
        elif command == "del":
            ch_addr = args.caddr
            ch_port = args.cport
            serf_client.delete_channel(ch_addr, ch_port)
        else:
            print "Unknown mode"
            return -1

    except argparse_actions.InvalidIp as e:
        print "IP address is invalid: {0}".format(e.ip)


if __name__ == "__main__":
    psng_serf_client_init()
