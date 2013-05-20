#!/usr/bin/python
import os
import sys
from optparse import OptionParser
from lxml import etree as ET
import ConfigParser
import hashlib
import gzip
import shutil
import time

XML_HEADER = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE comps PUBLIC "-//Red Hat, Inc.//DTD Comps info//EN" "comps.dtd">
<comps>
"""
XML_FOOTER = """</comps>
"""
DEFAULT_CONFIG_FILE = "./groups.conf"

def main():
  # Get Args and repositories from configfile and commandline
  arguments, repositories = checkArgs()
 
  # If desired, retrieve groups from an xml file and push them to
  # a set of directories. This is useful if you want to grab the
  # comps.xml file from an install cd and use them in this system.
  if arguments['import']:
    with open(arguments['importfrom'], "r") as import_from:
      exportGroups(import_from, arguments['importdir'])
 
  # This is a list of groups to be installed on the base system.
  kickstartGroups = ["PACKAGES=\""]
  
  for i in repositories:
    if arguments['verbose']:
      print "Processing:", i['name']
    categories = []
    groups = []
    
    # Get all of the groups from the defined directory
    groups.extend(groupsFromDirs(i['DirLocation']))
    categories.extend(categoriesFromDirs(i['DirLocation']))
    
    # Make sure that there are no duplicates or empty groups
    validate(groups, categories)

    # Generate a new xml file with these group definitions
    xml = writeToXML(groups, categories)
    if i['OutputFile']:
      writeToFile(xml, i['OutputFile'])
    if i['PushToWeb']:
      pushRepoData(i['WebDir'], xml)
    # Add any groups marked for kickstarting to the kickstart list
    kickstartGroups.extend(["@"+x['name']+"\n" for x in groups if x['kickstart'])

  kickstartGroups.append("\"")

  if arguments['PushToKickstart']:
    writeToFile(kickstartGroups, arguments['KickstartConfigLocation'])
    
def checkArgs():
  globalOptions = ["import", "importfrom", "importdir", "verbose", "configfile"]
  repositoryOptions = ["name", "DirLocation", "OutputFile", "PushToWeb", "WebDir", "PushToKickstart", "KickstartConfigLocation"]
  
  # globalOptions are read from the command line and from the config file. The commandline takes precedence.
  # repositoryOptions are read from their own sections in the config file only.
  parser = OptionParser(description='Generates group files for yum repositories')
  parser.add_option('--configfile', '-c', help="Sets the config file for all other options")
  parser.add_option('--importfrom', '-i', help="Selects a comps.xml file to parse and dump the contents into a directory format in <importdir>")
  parser.add_option('--importdir', '-d', help="Selects the directory to dumps the contents of <importfrom> into")
  parser.add_option('--listpackages', '-l', help="Prints a list of every package listed in a group", action="store_true")
  parser.add_option('--excludelist', '-e', help="File that contains a list of packages to exclude from all groups")
  parser.add_option('--verbose', '-v', help="Prints a more detailed rendition of what I am doing", action="store_true")
  parser.add_option('--listorphans', '-O', help="lists groups that aren't in any categories", action="store_true")
  (options, args) = parser.parse_args()
  arguments = options.__dict__
  
  config = ConfigParser.ConfigParser()
  if arguments['configfile']:
    config.readfp(open(arguments['configfile'], "r"))
  else:
    config.readfp(open(DEFAULT_CONFIG_FILE, "r"))
  if config.has_section("main"):
    for i in globalOptions:
      if config.has_option("main", i) and config.get("main", i) and not(arguments[i]):
        arguments[i] = config.get("main", i)
  files = [arguments['importfrom'], arguments['importdir'], arguments['configfile']]      
  repositories = []
  for i in config.sections():
    if not(i == "main"):
      for j in repositoryOptions:
        if config.has_option(i, j)):
          value = config.get(i, j)
          if value == "False" or value == "" or value == "false":
            value = False
          repository[i] = value
    if repository['PushToWeb']:
      files.append(repository['WebDir'])
    if repository['PushToKickstart']:
      files.append(repository['KickstartConfigLocation'])
    files.extend([repository['DirLocation'], repository['OutputFile']])
    repositories.append(repository)
    
  if not(all(arguments['importfrom'], arguments['importdir'])):
    sys.exit("Please supply both an xml file for me to look at and a directory for me to put things.")
  for i in [x in files if not(os.file.exists(x)) and x]:
    sys.exit("The file: ", i, " does not exist.")
  for i in repositories:
    if not(all(i['name'], i['DirLocation'])):
      sys.exit("Please specify the name and directory tree location of every repository.")
  return arguments, repositories
  
def exportGroups(fromFile, toDir):
  groups, categories = parseRhelComp(fromFile)
  validate(groups, categories)
  # This collects all of the lists of packages from every dictionary in categories.
  # Sorry it is a one-liner.
  claimed = reduce(lambda x,y:x+y['groups'], categories, [])
  unclaimed = [x in groups if not(x in claimed)]
  if unclaimed:
    categories.append({"groups":unclaimed, "name":"unclaimed", "id":"unclaimed", "description":"This is the category for groups not in other categories."})
  for i in [x in categories if x]:
    path = os.path.join(toDir, i['id'])
    if not(os.path.exists(path)):
      os.makedirs(path)
    description = i['id'] + "\n"
    description += i['name'] + "\n"
    description += i['description'] + "\n"
    writeToFile(description, os.path.join(toDir, i['id'], "CategoryDesc.txt"))
    for j in i['groups']:
      groupData = j['id'] + "\n"
      groupData += j['name'] + "\n"
      groupData += j['description'] + "\n"
      for k in j['packages']:
        groupData += k + "\n"
      writeToFile(groupData, os.path.join(toDir, i['id'], j['id'])
  
def parseRhelComp(rhelComps):
  tree = ET.parse(rhelComps)
  root = tree.getroot()
  groups = []
  if root.tag == "comps":
    for groupData in root:
      if groupData.tag == "group":
        group = {}
        group['description'] = groupData.find('description').text
        if not(group['description']):
          group['description'] = "This group needs no description"
        group['name'] = groupData.find('name').text
        # I hate xml...
        # This searches for the packagelist section, and returns the text from every packagereq line
        group['packages'] = [x.text for x in groupData.find('packagelist').findall('packagereq')]
        group['id'] = groupData.find('id').text
        groups.append(group)

    categories = []
    for categoryData in root:
      if categoryData.tag == "category":
        category = {}
        category['groups'] = [x.text for x in categoryData.find('grouplist').findall('groupid')]
        category['name'] = categoryData.find('name').text
        category['id'] = categoryData.find('id').text
        category['description'] = categoryData.find('description').text
        categories.append(category)
  else:
    sys.exit("This is not a valid redhat(c) comps.xml. I'm so sorry.")
  return groups, categories
  
def groupsFromDirs(directoryLocation):
  
def categoriesFromDirs(directoryLocation):
  
def validate(groups, categories):
  
def writeToXML(groups, categories):
  
def pushRepoData(webDir, xml):
  
    
def writeToFile(lineList, outFile):
  with open(outFile, "w") as file:
    for i in lineList:
      file.write(i)
      
main()