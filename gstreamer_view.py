import os

import gtk
import gst
import gobject
from pygtkhelpers.delegates import SlaveView


# We need to call threads_init() to ensure correct gtk operation with
# multi-threaded code (needed for GStreamer).
gobject.threads_init()
gtk.gdk.threads_init()


class GStreamerVideoView(SlaveView):
    """
    SlaveView for displaying GStreamer video sink
    """
    def __init__(self, pipeline):
        self.widget = gtk.DrawingArea()
        self.widget.connect('realize', self.on_realize)
        self.sink = None
        self.window_xid = None
        self.pipeline = pipeline

    def on_realize(self, widget):
        if not self.widget.window.has_native():
            # Note that this is required (at least for Windows) to ensure that the
            # DrawingArea has a native window assigned.  In Windows, if this is not
            # done, the video is written to the parent OS window (not a "window" in
            # the traditional sense of an app, but rather in the window manager
            # clipped rectangle sense).  The symptom is that the video will be drawn
            # over top of any widgets, etc. in the parent window.
            if not self.widget.window.ensure_native():
                raise RuntimeError, 'Failed to get native window handle'
        if os.name == 'nt':
            self.window_xid = self.widget.window.handle
        else:
            self.window_xid = self.widget.window.xid
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.enable_sync_message_emission()
        bus.connect("message", self.on_message)
        bus.connect("sync-message::element", self.on_sync_message)

    def on_message(self, bus, message):
        t = message.type
        if t == gst.MESSAGE_EOS:
            self.pipeline.set_state(gst.STATE_NULL)
        elif t == gst.MESSAGE_ERROR:
            err, debug = message.parse_error()
            print "Error: %s" % err, debug
            self.pipeline.set_state(gst.STATE_NULL)
    
    def on_sync_message(self, bus, message):
        if message.structure is None:
            return
        message_name = message.structure.get_name()
        if message_name == "prepare-xwindow-id":
            imagesink = message.src
            imagesink.set_property("force-aspect-ratio", True)
            gtk.gdk.threads_enter()
            if self.window_xid is None:
                raise ValueError, 'Invalid window_xid.  Ensure the '\
                    'DrawingArea has been realized.'
            imagesink.set_xwindow_id(self.window_xid)
            imagesink.expose()
            gtk.gdk.threads_leave()
            self.sink = imagesink
