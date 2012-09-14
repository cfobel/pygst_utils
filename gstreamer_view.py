import os
import time
from datetime import datetime

import gtk
import gst
import gobject
from pygtkhelpers.delegates import SlaveView
from pygtkhelpers.utils import gsignal


# We need to call threads_init() to ensure correct gtk operation with
# multi-threaded code (needed for GStreamer).
gobject.threads_init()
gtk.gdk.threads_init()


class GStreamerVideoPipelineManager(gobject.GObject):
    """
    SlaveView for displaying GStreamer video sink
    """
    gsignal('video-started', object)

    def __init__(self, force_aspect_ratio=True):
        super(GStreamerVideoPipelineManager, self).__init__()
        self.window_xid = None
        self.pipeline = None
        self.start_time = None
        self.sink = None
        self.force_aspect_ratio = force_aspect_ratio

    @property
    def pipeline(self):
        if not hasattr(self, '_pipeline'):
            self._pipeline = None
        return self._pipeline

    @pipeline.setter
    def pipeline(self, pipeline):
        if hasattr(self, '_pipeline') and self._pipeline:
            result = self._pipeline.set_state(gst.STATE_NULL)
            if hasattr(self, 'sink') and self.sink:
                self.sink.set_xwindow_id(0)
                del self.sink
            del self._pipeline
        self._pipeline = pipeline
        if self._pipeline:
            bus = self._pipeline.get_bus()
            bus.add_signal_watch()
            bus.enable_sync_message_emission()
            bus.connect("message", self.on_message)
            bus.connect("sync-message::element", self.on_sync_message)

    def on_message(self, bus, message):
        t = message.type
        if t == gst.MESSAGE_EOS:
            self.pipeline.set_state(gst.STATE_NULL)
        elif t == gst.MESSAGE_STATE_CHANGED:
            if message.src == self.pipeline\
                    and message.structure['new-state'] == gst.STATE_PLAYING:
                self.start_time = datetime.fromtimestamp(
                    self.pipeline.get_clock().get_time() * 1e-9)
                self.emit('video-started', self.start_time)
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
            if self.force_aspect_ratio:
                imagesink.set_property("force-aspect-ratio", True)
            if self.window_xid is None:
                raise ValueError, 'Invalid window_xid.  Ensure the '\
                    'DrawingArea has been realized.'
            imagesink.set_xwindow_id(self.window_xid)
            imagesink.expose()
            self.sink = imagesink


class GStreamerVideoView(SlaveView):
    """
    SlaveView for displaying GStreamer video sink
    """

    def __init__(self, force_aspect_ratio=True):
        super(GStreamerVideoView, self).__init__()
        self.widget = gtk.DrawingArea()
        self.widget.connect('realize', self.on_realize)
        self.window_xid = None
        self.force_aspect_ratio = force_aspect_ratio
        self._set_window_title = False

    def show_and_run(self):
        self._set_window_title = True
        super(GStreamerVideoView, self).show_and_run()

    def on_realize(self, widget):
        if not self.widget.window.has_native():
            # Note that this is required (at least for Windows) to ensure that
            # the DrawingArea has a native window assigned.  In Windows, if this
            # is not done, the video is written to the parent OS window (not a
            # "window" in the traditional sense of an app, but rather in the
            # window manager clipped rectangle sense).  The symptom is that the
            # video will be drawn over top of any widgets, etc. in the parent
            # window.
            if not self.widget.window.ensure_native():
                raise RuntimeError, 'Failed to get native window handle'
        if os.name == 'nt':
            self.window_xid = self.widget.window.handle
        else:
            self.window_xid = self.widget.window.xid
        # Copy window xid to clipboard
        clipboard = gtk.Clipboard()
        clipboard.set_text(str(self.window_xid))
        if self._set_window_title:
            self.widget.parent.set_title('[window_xid] %s' % self.window_xid)
        print '[window_xid] %s' % self.window_xid
