
import os
import re
import socket
import time

class HostapdCtrl:


    def __init__(self, ifname):
        # Arbitrary local socket name we bind to; this is needed because when
        # we ATTACH to the hostapd control socket, it saves this name so it
        # can send back events.
        self._sockaddr_local = "/tmp/hostapd_ctrl.%d" % (os.getpid(), )
        try:
            os.unlink(self._sockaddr_local)
        except:
            pass # it wasn't there, okay
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.sock.bind(self._sockaddr_local)
        self.sock.setblocking(0)
        # hostapd control socket. Connect to this to send commands to, and get
        # responses and events from, hostapd. If the network interface used by
        # hostapd changes, this must change. (It may be better to just pick
        # the first socket in the directory.)
        self._sockaddr_remote = "/var/run/hostapd/%s" % (ifname, )


    # Attach to hostapd control socket.
    #
    # When hostapd gets the ATTACH command, it saves the address of the socket
    # that sent it (_sockaddr_local), then any asynchronous events that show
    # up (like pin-needed) get sent there. There can be more than one client
    # attached at the same time; hostapd keeps a list.
    #
    # Returns:
    #   True if attached
    #   False if not attached (timeout or error)
    def attach(self, timeout_s):
        self.sock.settimeout(0.1)
        while True:
            try:
                self.sock.sendto("ATTACH", self._sockaddr_remote)
            except:
                # control socket probably not there
                pass
            else:
                pkt = self.sock.recv(256)
                # On success, we get "OK\n" (3 chars)
                if pkt and len(pkt) == 3 and pkt.find("OK") != -1:
                    return True
            timeout_s -= 1.0
            if timeout_s < 0.0:
                return False
            time.sleep(1.0)
        # end while True


    # Receive message from hostapd.
    def recv(self):
        return self.sock.recv(256)

    # Parse message from hostapd.
    #
    # The PIN request packet from hostapd looks something like this (with no
    # newline; one space separates the two lines as shown here):
    #
    # <3>WPS-PIN-NEEDED 7d4c3eba-141a-54bc-9345-7bc0d6c27f04 00:15:6d:85:ce:b7
    # [My Solo|3D Robotics|Solo|Solo-1|S-1234567890|0-00000000-0]
    #
    # The UUID 7d4c3eba-141a-54bc-9345-7bc0d6c27f04 is generated by Solo. It
    # is based on the MAC address somehow, but since we don't know how it is
    # generated (or whether it will be the same over time), it is only used
    # where necessary.
    #
    # The MAC 00:15:6d:85:ce:b7 comes from Solo's WiFi card.
    #
    # Everything in the [brackets] comes from Solo's wpa_supplicant.conf file:
    # [device_name|manufacturer|model_name|model_number|serial_number|device_type]
    #
    # Returns:
    #   9-tuple for WPS-PIN-NEEDED
    #       ("WPS-PIN-NEEDED", uuid, mac, device_name, manufacturer,
    #        model_name, model_number, serial_number, device_type)
    #   1-tuple for other message types
    #       ("MESSAGE-TYPE", )
    #   1-tuple if message can't be parsed containing entire packet
    def parse(self, pkt):

        regexp = "<3>WPS-PIN-NEEDED ([0-9a-fA-F\-]+) ([0-9a-fA-F:]+) \[(.*?)\|(.*?)\|(.*?)\|(.*?)\|(.*?)\|(.*?)\]"
        m = re.match(regexp, pkt)
        if m:
            fields = m.groups()
            if len(fields) == 8:
                return ("WPS-PIN-NEEDED", ) + fields
            else:
                return (pkt, )

        # add other messages here as needed

        # default: just parse out the message type
        regexp = "<[0-9]+>(.+?) "
        m = re.match(regexp, pkt)
        if m:
            return (m.group(1), )

        return (pkt, )


    # Send pin reply
    def send_pin(self, uuid, pin):
        pin_reply = "WPS_PIN %s %d" % (uuid, pin)
        self.sock.sendto(pin_reply, self._sockaddr_remote)
