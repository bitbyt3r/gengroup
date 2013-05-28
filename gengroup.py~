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
 
  for i in repositories:
    # This is a list of groups to be installed on the base system.
    kickstartGroups = ["PACKAGES=\""]
    
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
    if arguments['verbose']:
      print "Wrote new xml files to:" + os.path.join(i['WebDir'], "repodata/")

    # Add any groups marked for kickstarting to the kickstart list
    kickstartGroups.extend(["@"+x['name']+"\n" for x in groups])

    kickstartGroups.append("\"")

    if i['PushToKickstart']:
      writeToFile(kickstartGroups, i['KickstartConfigLocation'])
    
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
  if arguments['verbose']:
    print "Going in verbose mode..."
  else:
    arguments['verbose'] = False
  
  config = ConfigParser.ConfigParser()
  if arguments['configfile']:
    config.readfp(open(arguments['configfile'], "r"))
  else:
    config.readfp(open(DEFAULT_CONFIG_FILE, "r"))
  if config.has_section("main"):
    for i in globalOptions:
      if config.has_option("main", i) and config.get("main", i) and not(i in arguments.keys() and arguments[i]):
        arguments[i] = config.get("main", i)
  files = []
  if bool(arguments['importfrom']) or bool(arguments['importdir']):
    arguments['import'] = True
    files.extend([arguments['importfrom'], arguments['importdir']])
  else:
    arguments['import'] = False
  if arguments['configfile']:
    files.append(arguments['configfile'])
    
  repositories = []
  for i in config.sections():
    if not(i == "main"):
      repository = {}
      for j in repositoryOptions:
        if config.has_option(i, j):
          value = config.get(i, j)
          if value == "False" or value == "" or value == "false":
            value = False
          repository[j] = value
      if not("name" in repository.keys()):
        repository['name'] = j
      if "PushToWeb" in repository.keys() and repository['PushToWeb']:
        files.append(repository['WebDir'])
      else:
        repository['PushToWeb'] = False
      if "PushToKickstart" in repository.keys() and repository['PushToKickstart']:
        files.append(repository['KickstartConfigLocation'])
      else:
        repository['PushToKickstart'] = False
      if not("DirLocation" in repository.keys() and "OutputFile" in repository.keys()):
        sys.exit("Please provide an input directory and an output file for " + str(i))
      files.append(repository['DirLocation'])
      repositories.append(repository)
    
  if bool(arguments['importfrom']) !=  bool(arguments['importdir']):
    sys.exit("Please supply both an xml file for me to look at and a directory for me to put things.")
  for i in [x for x in files if not(x and os.path.exists(x))]:
    sys.exit("The file: " + str(i) + " does not exist.")
  for i in repositories:
    if not(i['name'] and i['DirLocation']):
      sys.exit("Please specify the name and directory tree location of every repository.")
  return arguments, repositories
  
def exportGroups(fromFile, toDir):
  groups, categories = parseRhelComp(fromFile)
  validate(groups, categories)
  # This collects all of the lists of packages from every dictionary in categories.
  # Sorry it is a one-liner.
  claimed = reduce(lambda x,y:x+y['groups'], categories, [])
  unclaimed = [x for x in groups if not(x in claimed)]
  if unclaimed:
    categories.append({"groups":unclaimed, "name":"unclaimed", "id":"unclaimed", "description":"This is the category for groups not in other categories."})
  for i in [x for x in categories if x]:
    path = os.path.join(toDir, i['id'])
    if not(os.path.exists(path)):
      os.makedirs(path)
    description = i['id'] + "\n"
    description += i['name'] + "\n"
    description += i['description'] + "\n"
    writeToFile(description, os.path.join(toDir, i['id'], "CategoryDesc.txt"))
    for j in groups:
      if j['id'] in i['groups']:
        groupData = j['id'] + "\n"
        groupData += j['name'] + "\n"
        groupData += j['description'] + "\n"
        for k in j['packages']:
          groupData += k + "\n"
        writeToFile(groupData, os.path.join(toDir, i['id'], j['id']))
  
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
  
def groupsFromDirs(groupDir):
  groupFiles = []
  for root, dirs, files in os.walk(groupDir):
    if not(".svn" in root):
      groupFiles.extend([(root,x) for x in files])

  groups = []
  for root, filename in groupFiles:
    if not("CategoryDesc.txt" in filename):
      with open(root+"/"+filename, "r") as file:
        lines = file.readlines()
        if len(lines) < 4:
          sys.exit("Invalid group file: " + filename + "\nIt is too short.")
        id = lines[0].strip()
        name = lines[1].strip()
        description = lines[2].strip()
        packages = [x.strip() for x in lines[3:]]
        groups.append({"id":id, "name":name, "description":description, "packages":packages})
  return groups
  
def categoriesFromDirs(directory):
  categories = []
  for i in [name for name in os.listdir(directory) if os.path.isdir(directory+"/"+name) and not(".svn" in name)]:
    category = {}
    category['groups'] = [name for name in os.listdir(directory+"/"+i) if (not(".svn" in name) and not("CategoryDesc.txt" in name) and not(os.path.isdir(directory+"/"+i+"/"+name)))]
    with open(directory + "/" + i + "/CategoryDesc.txt") as categoryDescFile:
      categoryDesc = categoryDescFile.readlines()
      category['id'] = categoryDesc[0].strip()
      category['name'] = categoryDesc[1].strip()
      category['description'] = categoryDesc[2].strip()
      categoryDescFile.close()
    categories.append(category)
  return categories
  
def validate(groups, categories):
  # remove empty packages
  for i in groups:
    i['packages'] = [x for x in i['packages'] if x]
  # remove empty group names
  for i in categories:
    i['groups'] = [x for x in i['groups'] if x]
  # remove empty groups
  for i in [x for x in groups if not(x['packages'])]:
    print "Removed: ", i['name'], " because it had no packages."
  groups = [x for x in groups if x['packages']]
  # remove empty categories
  iterator = list(categories)
  for i in iterator:
    for j in i['groups']:
      if not([x for x in groups if x['id'] in i['groups']]):
        categories.remove(i)
        if verbose:
          print "Removed: ", i['name'], " because it had no groups."
  # throw error on group with duplicate id
  for i in xrange(len(groups)):
    for j in xrange(i + 1, len(groups)):
      if groups[i]['id'] == groups[j]['id']:
        sys.exit("The groups: " + groups[i]['name'] + " and " + groups[j]['name'] + " have the same id. Please adjust accordingly.")
  # throw error on category with duplicate id
  for i in xrange(len(categories)):
    for j in xrange(i + 1, len(categories)):
      if categories[i]['id'] == categories[j]['id']:
        sys.exit("The categories: " + categories[i]['name'] + " and " + categories[j]['name'] + " have the same id. Please adjust accordingly.")
  return groups, categories
  
def writeToXML(groups, categories):
  xml = XML_HEADER
  for i in groups:
    xml += genGroupXML(i)
  for i in categories:
    xml += genCategoryXML(i)
  xml += XML_FOOTER
  return xml
  
def genGroupXML(group):
  xml = " <group>\n"
  xml += "  <id>" + group['id'] + "</id>\n"
  xml += "  <default>False</default>\n"
  xml += "  <uservisible>True</uservisible>\n"
  xml += "  <name>" + group['name'] + "</name>\n"
  xml += "  <description>" + group['description'] + "</description>\n"
  xml += "   <packagelist>\n"
  for i in group['packages']:
    xml += "    <packagereq type=\"mandatory\">" + i + "</packagereq>\n"
  xml += "   </packagelist>\n"
  xml += " </group>\n"
  return xml
  
def genCategoryXML(category):
  xml = " <category>\n"
  xml += "   <id>" + category['id'] + "</id>\n"
  xml += "   <name>" + category['name'] + "</name>\n"
  xml += "   <description>" + category['description'] + "</description>\n"
  xml += "   <grouplist>\n"
  for i in category['groups']:
    xml += "     <groupid>" + i + "</groupid>\n"
  xml += "   </grouplist>\n </category>\n"
  return xml
  
def pushRepoData(webDir, xml):
  print "WebDir:", webDir
  for root, dirs, files in os.walk(webDir+"/repodata/"):
    for name in files:
      if "comps" in name:
        os.remove(os.path.join(root, name))
        
  # Calculate length and sha1 hash of raw xml
  m = hashlib.sha1()
  m.update(xml)
  xmlLength = len(xml)
  xmlHash = m.hexdigest()
  
  # Gzip and store xml in a temporary location
  gzippedXMLFile = gzip.open("/tmp/comps-file.gz", "wb")
  gzippedXMLFile.write(xml)
  gzippedXMLFile.close()
  
  # Calculate length and hash of gzipped xml file
  m = hashlib.sha1()
  with open("/tmp/comps-file.gz") as gzippedXMLFile:
    fileContents = gzippedXMLFile.read()
  m.update(fileContents)
  gzipLength = len(fileContents)
  gzipHash = m.hexdigest()
  
  # Move the gzipped file into the repodata directory, and place the raw xml file there as well
  shutil.copyfile("/tmp/comps-file.gz", os.path.join(webDir, "repodata", gzipHash+"-comps-csee.xml.gz"))
  writeToFile(xml, os.path.join(webDir,"repodata", xmlHash+"-comps-csee.xml"))
  
  # Update the description of these two prior files contained
  # in the /repodata/repomd.xml
  tree = ET.parse(os.path.join(webDir, "repodata/repomd.xml"))
  root = tree.getroot()
  # Namespaces suck.
  namespace = "{http://linux.duke.edu/metadata/repo}"
  # Find and replace the appropriate values for checksum, checksum type, location, timestamp, and size
  for i in root.findall(namespace+"data"):
    if i.get("type") == 'group':
      i.find(namespace+"checksum").text = xmlHash
      i.find(namespace+"checksum").set("type", "sha")
      i.find(namespace+"location").set("href", "repodata/"+xmlHash+"-comps-csee.xml")
      i.find(namespace+"timestamp").text = "%.2f" % time.time()
      i.find(namespace+"size").text = str(xmlLength)
    if i.get("type") == 'group_gz':
      i.find(namespace+"checksum").text = gzipHash
      i.find(namespace+"checksum").set("type", "sha")
      i.find(namespace+"open-checksum").text = xmlHash
      i.find(namespace+"location").set("href", "repodata/"+gzipHash+"-comps-csee.xml.gz")
      i.find(namespace+"timestamp").text = "%.2f" % time.time()
      i.find(namespace+"size").text = str(gzipLength)
  # Write the resulting xml with the appropriate formatting back into the repomd.xml file
  tree.write(os.path.join(webDir, "repodata/repomd.xml"), xml_declaration=True, encoding="UTF-8", pretty_print=True)
    
def writeToFile(lineList, outFile):
  with open(outFile, "w") as file:
    for i in lineList:
      file.write(i)
      
main()
