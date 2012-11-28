#!/usr/bin/env python
"""This is the base library that can used to run various OSM bots
which are implemented as plugins"""

import sys
from xml.sax import make_parser
import argparse
from pyxbot import OSMHandler
from os import remove
import codecs
import expansions

def add_or_incr(dct, item):
    """Takes a dictionary and item and increments the number on that
    item in the dictionary (like a set only with a counter)"""
    if dct.has_key(item):
        dct[item] = dct[item] + 1
    else:
        dct[item] = 1

road_types = expansions.road_types
directions = expansions.directions

class TigerRoadExpansionHandler(OSMHandler):
    """This is the TIGER expansion class"""
    def __init__(self, file_prefix):
        OSMHandler.__init__(self, file_prefix)
        self.selected = 0
        self.num_fixed = 0
        self.checkme_ways = []
        self.unrecognized_tags = {}
        self.unrecognized_direction_tags = {}
        self.ambigious_expansions = {}

    def get_road_type(self, suffix = ""):
        """Retrieves the road type from the element's tiger tags"""
        tags = self.tags
        name = tags.get('name' + suffix)
        namel = name.split()
        # If we have a name_type that we haven't seen, store it.
        # If the name is ambigious, store it.
        road_type = self.tags.get('tiger:name_type' + suffix)
        if not road_type:
            return
        if road_type not in road_types:
            add_or_incr(self.unrecognized_tags, road_type)
            # We'll only report this if it's really unique
            if road_type not in road_types.values():
                self.checkme_ways.append(
                    {'name': tags.get('name'),
                     'id': self.attrs['id'],
                     'reason': 'Unknown road_type (%s)' % road_type})
            road_type = None
        elif namel.count(road_type) > 1:
            add_or_incr(self.ambigious_expansions, name)
            self.checkme_ways.append({'name': tags.get('name'),
                                      'id': self.attrs['id'],
                                      'reason': 'Ambigious expansion'})
            road_type = None
        elif namel.count(road_type) < 1:
            if not namel.count(road_types[road_type]) >= 1:
                self.checkme_ways.append(
                    {'name': tags.get('name'),
                     'id': self.attrs['id'],
                     'reason': 'Road type (%s) not in name' % road_type})
            road_type = None
        return road_type

    def get_direction_prefix(self, suffix=""):
        """Retrieves the direction prefix from object using the tiger tags"""
        name = self.tags.get('name' + suffix)
        namel = name.split()
        # Same with the direction tags prefix
        dir_tag_prefix = self.tags.get('tiger:name_direction_prefix' + suffix)
        if not dir_tag_prefix:
            return
        if not dir_tag_prefix in directions:
            add_or_incr(self.unrecognized_direction_tags, dir_tag_prefix)
            dir_tag_prefix = None
        else:
            if namel.count(dir_tag_prefix) > 1:
                add_or_incr(self.ambigious_expansions, name)
                dir_tag_prefix = None
            elif namel.count(dir_tag_prefix) < 1:
                dir_tag_prefix = None
        return dir_tag_prefix

    def get_direction_suffix(self, suffix=""):
        """Retrieves the direction suffix from object using the tiger tags"""
        tags = self.tags
        name = tags.get('name' + suffix)
        namel = name.split()
        dir_tag_suffix = tags.get('tiger:name_direction_suffix' + suffix)
        if not dir_tag_suffix:
            return
        if not dir_tag_suffix in directions:
            add_or_incr(self.unrecognized_direction_tags, dir_tag_suffix)
            dir_tag_suffix = None
        else:
            if namel.count(dir_tag_suffix) > 1:
                add_or_incr(self.ambigious_expansions, name)
                dir_tag_suffix = None
            elif namel.count(dir_tag_suffix) < 1:
                dir_tag_suffix = None
        return dir_tag_suffix

    def selectElement(self):
        tags = self.tags
        # We only care about ways with highway=* tags that have a name
        if not (self.type == 'way' and tags.has_key('highway') and
                tags.has_key('name')):
            return

        suffixes = ['', '_1', '_2', '_3', '_4', '_5', '_6', '_7', '_8', '_9']
        for s in suffixes:
            if tags.get('name%s' % s) and tags.get('tiger:name%s_base' %s):
                return True

    def fix_name(self, suffix=""):
        """Fix a "name" tag, taking an optional suffix (ala '_1')"""
        tags = self.tags
        name = tags['name' + suffix]
        namel = name.split()

        short_road_type = self.get_road_type(suffix)        
        if short_road_type:
            long_road_type = road_types[short_road_type]
            indx = namel.index(short_road_type)
            namel[indx] = long_road_type

        dir_tag_prefix = self.get_direction_prefix(suffix)
        if dir_tag_prefix:
            try:
                long_direction = directions[dir_tag_prefix]
            except KeyError:
                self.checkme_ways.append(
                    {'name': tags.get('name'),
                     'id': self.attrs['id'],
                     'reason': 'Direction prefix (%s) not in directions list' \
                         % dir_tag_prefix})
            try:
                # If we want to be more clever here, we can use the
                # name_base and index off that, ala:
                # indx = namel[:namel.index(tags['tiger:name_base' + suffix])]
                indx = namel.index(dir_tag_prefix)
                namel[indx] = long_direction
            except ValueError:
                self.checkme_ways.append(
                    {'name': tags.get('name'),
                     'id': self.attrs['id'],
                     'reason': 'Direction prefix (%s) not in name' \
                         % dir_tag_prefix})

        dir_tag_suffix = self.get_direction_suffix(suffix)
        if dir_tag_suffix:
            try:
                long_direction = directions[dir_tag_suffix]
            except KeyError:
                self.checkme_ways.append(
                    {'name': tags.get('name'),
                     'id': self.attrs['id'],
                     'reason': 'Direction suffix (%s) not in directions list' \
                         % dir_tag_prefix})
            try:
                indx = namel.index(dir_tag_suffix)
                namel[indx] = long_direction
            except ValueError:
                self.checkme_ways.append(
                    {'name': tags.get('name'),
                     'id': self.attrs['id'],
                     'reason': 'Direction suffix (%s) not in name' \
                         % dir_tag_suffix})

        newname = ' '.join(namel)
        if newname != name:            
            self.tags['name' + suffix] = newname
        if not self.fixed:
            self.bump_version()
            self.remove_user_changeset()
            self.fixed = True
            self.num_fixed += 1

    def remove_useless_tags(self):
        """Removes tags that would be removed from JOSM or Potlatch"""
        tags = self.tags
        for tag in ["created_by", "tiger:upload_uuid", "tiger:tlid",
                    "tiger:source", "tiger:separated", "odbl", "odbl:note"]:
            if tags.has_key(tag):
                del(tags[tag])

    def transformElement(self):
        suffixes = ['', '_1', '_2', '_3', '_4', '_5', '_6', '_7', '_8', '_9']
        for s in suffixes:
            if self.tags.get('name' + s):
                self.fix_name(s)
        if self.fixed:
            self.remove_useless_tags()

    def endDocument(self):
        self._close()
        if self.num_fixed == 0:
            remove(self.fname)

def main():
    """Function run by command line"""
    argparser = argparse.ArgumentParser(description="Tiger expansion bot")
    argparser.add_argument('--infile', dest = 'infname',
                           help = 'The input filename')
    argparser.add_argument('--outdir', dest = 'outdirname',
                           default = 'processed', help = 'The output directory')
    argparser.add_argument('--checkways', dest = 'checkways_fname',
                           default = 'ways.csv',
                           help = "Unfixable way csv file")
    args = argparser.parse_args()
    if not args.infname:
        argparser.print_help()
        return -1
    if args.infname == '-':
        input_file = sys.stdin
        args.infname = 'expansion'
    else:
        input_file = open(args.infname, 'r')

    if not args.outdirname:
        args.outdirname = args.infname
    dirname = args.outdirname

    parser = make_parser()
    handler = TigerRoadExpansionHandler(dirname)
    parser.setContentHandler(handler)
    parser.parse(input_file)

    #print "%d total roads" % handler.roads
    #print "%d fixed roads" % handler.num_fixed
    #print "%d unrecognized tags" % len(handler.unrecognized_tags)
    #print "%d ambigious road names" % len(handler.ambigious_expansions)
    #print
    #print "Ambigious Names"
    #print "================"
    #for key, val in handler.ambigious_expansions.items():
    #    print "%s (%s)" % (key, val)
    
    #print
    
    #print "Unrecognized Tags"
    #print "================="
    #for key, val in handler.unrecognized_tags.items():
    #    print "%s (%s)" % (key, val)
    if handler.checkme_ways:
        outfile = codecs.open(args.checkways_fname, 'w', 'utf-8')
        outfile.write('ID,Name,Reason\n')
        for i in handler.checkme_ways:
            oid, name, reason = i['id'], i['name'], i['reason']
            if ',' in name:
                name = '"%s"' % name
            outfile.write("%s,%s,%s\n" % (oid, name, reason))
        outfile.close()
                     
if __name__ == '__main__':
    sys.exit(main())
