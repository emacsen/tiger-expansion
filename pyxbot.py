from xml.sax.handler import ContentHandler
import os
import codecs
from xml.sax.saxutils import escape

class OSMHandler(ContentHandler):
    """This is a base OSMHandler class which sets up the XML parsing, etc.

You will want to override the selectElement and transformElement
functions"""
    def __init__(self, file_prefix):
        self.path = file_prefix
        self.file_prefix = file_prefix
        self.object_counter = 0
        self.clear()
        self.max_objects_per_file = 1000
        self.file_counter = 0
        self.out = None
        self.fixed = None

    def _open(self):
        if not os.path.isdir(self.path):
            os.mkdir(self.path)
        #fh = codecs.open(self.path + '/' + "%s_%04d.osm" %
        #          (self.file_prefix, self.file_counter), 'w', "utf-8")
        self.fname = self.path + '/' + "%04d.osm" % self.file_counter
        #print "Opening %s" % self.fname
        fh = codecs.open(self.fname, 'w', "utf-8")
        self.out = fh
        self.out.write('<?xml version=\'1.0\' encoding=\'UTF-8\'?>\n')
        self.out.write('<osm version="0.6" generator="pyxbot">\n')

    def _close(self):
        #print "Closing " + self.fname
        self.out.write('</osm>\n')
        self.out.flush()
        self.out.close()
        self.out = None
        self.object_counter = 0
        self.file_counter = self.file_counter + 1

    def bump_version(self):
        self.attrs['version'] = str(int(self.attrs['version']) + 1)
        self.attrs['version'] = str(int(self.attrs['version']) + 1)

    def remove_user_changeset(self):
        if self.attrs.get('changeset'):
            del(self.attrs['changeset'])
        if self.attrs.get('uid'):
            del(self.attrs['uid'])
        if self.attrs.get('user'):
            del(self.attrs['user'])
        if self.attrs.get('timestamp'):
            del(self.attrs['timestamp'])

    # The output methods don't do any kind of data validation
    def _str_node(self):
        "Return a node as a string"
        if self.tags:
            s = u'<node %s >\n' % ' '.join([u'%s="%s"' % (x,y)
                                            for x,y in self.attrs.items()])
            for key,val in self.tags.items():
                s += u' <tag k="%s" v="%s" />\n' % (escape(key), escape(val))
            s += u'</node>'
        else:
            s = u'<node %s />\n' % ' '.join(['%s="%s"' % (x,y)
                                            for x,y in self.attrs.items()])
        return s

    def _str_way(self):
        "Output a way as a string"
        s = u'<way %s >\n' % ' '.join([u'%s="%s"' % (x, y)
                                       for x, y in self.attrs.items()])
        for nodeid in self.nodes:
            s += u' <nd ref="%s" />\n' % nodeid
        for key, val in self.tags.items():
            s += u' <tag k="%s" v="%s" />\n' % (escape(key), escape(val))
        s += u'</way>\n'
        return s

    def _str_relation(self):
        if self.members or self.tags:
            s = u'<relation %s >\n' % ' '.join([u'%s="%s"' % (x, y)
                                                for x, y in self.attrs.items()])
            for member in members:
                s += u' <member %s />\n' % ' '.join(['%s="%s"' % (x,y)
                                                     for x,y in member.items()])
            for key, val in self.tags.items():
                s += u' <tag k="%s" v="%s" />\n' % (escape(key), escape(val))
            s += u'</relation>\n'
        else:
            s = u'<relation %s />\n' % ' '.join([u'%s="%s"' % (x, y)
                                                 for x, y in self.attrs.items()])
        return s
    def emit(self):
        "Output the current element"
        if self.type == 'node':
            s = self._str_node()
        elif self.type == 'way':
            s = self._str_way()
        elif self.type == 'relation':
            s = self._str_relation()
        self.out.write(s)

    def clear(self):
        "Initialize the state machine"
        self.type = None
        self.tags = {}
        self.nodes = []
        self.members = []
        self.attrs = {}
        self.fixed = None

    def startElement(self, tag, attrs):
        "This function is called at the start of the element (as per SAX)"
        if tag == 'node':
            self.type = 'node'
            self.attrs = dict(attrs)
        elif tag == 'way':
            self.type = 'way'
            self.attrs = dict(attrs)
        elif tag == 'relation':
            self.type = 'relation'
            self.attrs = dict(attrs)
        elif tag == 'tag':
            self.tags[attrs.get('k')] = attrs.get('v')
        elif tag == 'member':
            self.members.append(attrs.copy())
        elif tag == 'nd':
            self.nodes.append(attrs.get('ref'))

    def selectElement(self):
        """Select whether or not we care about the OSM object (True or
False). Override this function in your handler"""
        return False

    def transformElement(self):
        """Transform the element. Override this function in your
handler"""
        pass

    def deleteElement(self):
        """Returns the string to delete the element. Please use with
caution!"""
        self.out.write('<delete version="%s" generator="%s">\n' %
                       (VERSION, BOTNAME))
        self.emit()
        self.out.write('</delete>\n')

    def endElement(self, tag):
        """As per the SAX handler, this method is where any work is
done. You may want to override it, but probably not"""
        # If there's no open output, we need to open it
        if not self.out:
            self._open()
        if tag == 'way':
            self.nodes = tuple(self.nodes)
        elif tag == 'relation':
            self.members = tuple(self.members)
        if tag == 'node' or tag == 'way' or tag == 'relation':
            if self.selectElement():
                self.transformElement()
                if self.fixed:
                    self.emit()
                self.object_counter = self.object_counter + 1
                if self.object_counter >= self.max_objects_per_file:
                    self._close()
            self.clear()

    def endDocument(self):
        self._close()
