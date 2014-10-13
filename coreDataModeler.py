# Manticore
# Copyright (C) 2013, Collin Schupman at Yeti LLC

# This is a script to update an exisiting CoreDataModel with a given JSON file

# Assumes JSON is in format : TODO->Write format

# Please pass in contents file from your xcode project, located here:
# project_name.xcdatamodeld
#    project_name.xcdatamodel
#       contents (XML)
# this script will make appropiate changes and update the file

# TODO:
#
# add in interactive session to get JSON and XML to update
# handle O2O case
# handle O2N case?
# test array of primitive case
# correctly resize elements, dynamically

import sys
import json
import StringIO
from lxml import etree
from xml.dom import minidom
import shutil

# Conversions for use in CoreData
DATA_TYPES = {
    "date"       : "Date",
    "datetime"   : "Date",
    "int"        : "Integer 32",
    "integer"    : "Integer 32",
    "integer16"  : "Integer 16",
    "integer32"  : "Integer 32",
    "integer64"  : "Integer 64",
    "decimal"    : "Decimal",
    "double"     : "Double",
    "real"       : "Double",
    "float"      : "Float",
    "string"     : "String",
    "text"       : "String",
    "boolean"    : "Boolean",
    "array"      : "Transformable"
}

# Database Relationships
RELATIONSHIPS = set({
    "O2O",
    "M2M",
    "O2M"
})

# A little logic to to make plural words more readable
# this won't cover everything, there's a few python libraries out there you could use: https://pypi.python.org/pypi/inflect
def get_word_plural(word):
    if word.endswith("y"):
        return word.lower()[:-1] + 'ies'
    else:
        return word.lower() + 's'

# Adds an elements branch and element leaf for each object in the JSON file
# TODO: come up with better way to compute height/position
def add_elements(model, objects):
    elements = etree.SubElement(model, "elements")
    for obj in objects:
        element = etree.SubElement(elements, "element", name = obj.keys()[0][1:])
        element.set("positionX", "0")
        element.set("positionY", "0")
        element.set("width", "128")
        element.set("height", "600")

# Sets up and returns a relationship between these two entities with all basic attributed filled in
def get_basic_relationship(entity, relationship_name, destination_entity, inverse_name, inverse_entity):
    relationship = etree.SubElement(entity, "relationship", name = relationship_name)
    relationship.set("optional", "YES")
    relationship.set("deletionRule", "Nullify")
    relationship.set("destinationEntity", destination_entity)
    relationship.set("syncable", "YES")
    relationship.set("inverseName", inverse_name)
    relationship.set("inverseEntity", inverse_entity)
    return relationship

# it seems redundant that we pass around the entities as well as their names then also get their names again from the entity in the following functions
# Creates a one relationship between these two entities
def add_one_relationship(entity_one, entity_two, entity_one_name, entity_two_name):
    relationship = get_basic_relationship(entity_one, entity_two_name, entity_two.get('name'), entity_one_name, entity_two.get('name'))
    relationship.set("minCount", "1")
    relationship.set("maxCount", "1")

# Creates a many relationship between these two entities
def add_many_relationship(entity_one, entity_two, entity_one_name, entity_two_name):
    relationship = get_basic_relationship(entity_one, entity_two_name, entity_two.get('name'), entity_one_name, entity_two.get('name'))
    relationship.set("ordered", "YES")
    relationship.set("toMany", "YES")

# Adds O2M relationships between these two entities
def add_M2M_relationships(entity_one, entity_two):
    entity_one_name = get_word_plural(entity_one.get('name'))
    entity_two_name = get_word_plural(entity_two.get('name'))

    add_many_relationship(entity_one, entity_two, entity_one_name, entity_two_name)
    add_many_relationship(entity_two, entity_one, entity_two_name, entity_one_name)

# Adds O2M relationships between these two entities
def add_O2M_relationships(one_entity, many_entity):
    one_entity_name = one_entity.get('name').lower()
    many_entity_name = get_word_plural(many_entity.get('name'))
    add_many_relationship(one_entity, many_entity, one_entity_name, many_entity_name)
    add_one_relationship(many_entity, one_entity, many_entity_name, one_entity_name)

# Adds relationships and inverse relationships for each required entity
# Currently only supports M2M, O2M. TODO: Add in O2O, possibly others
def add_relationships(model, objects):
    for obj in objects:
        obj_name = obj.keys()[0]
        obj_fields = obj[obj_name]
        for key, value in obj_fields.iteritems():

            values = value.split(",")
            # I think it's `optional` not `optionals` that we put in the schema files unless you want to change the wording
            if "optionals" in values:
                values.remove("optionals")
            if "primarykey" in values:
                values.remove("primarykey")

            # This isn't the most bulletproof way to do this if we ever want to add a new definition to the schema
            # Might be better to loop over every value in values and see if it equals O2M or M2M?
            # These two if/elif blocks are also identical minus the function being called, you could DRY this up
            if values[0] == "O2M":
                one_entity = None
                many_entity = None
                for entity in model.iter("entity"):
                    if entity.get('name') == obj_name[1:]:
                        many_entity = entity
                    elif entity.get('name') == values[1][1:]:
                        one_entity = entity
                add_O2M_relationships(one_entity, many_entity)
            elif values[0] == "M2M":
                entity_one = None
                entity_two = None
                for entity in model.iter("entity"):
                    if entity.get('name') == obj_name[1:]:
                        entity_one = entity
                    elif entity.get('name') == values[1][1:]:
                        entity_two = entity
                add_M2M_relationships(entity_one, entity_two)
    
# Adds attributes to the given entity for its name and type
def add_entity_attribute(entity, name, att_type):
    attribute = etree.SubElement(entity, "attribute", name = name)
    attribute.set("optional", "YES")
    attribute.set("attributeType", att_type)
    attribute.set("syncable", "YES")

# Adds entities for each object in the JSON tree
def add_entities(model, objects):
    for obj in objects:
        obj_name = obj.keys()[0]
        entity = etree.SubElement(model, "entity", name = obj_name[1:])
        obj_fields = obj[obj_name]

        for key, value in obj_fields.iteritems():
            values = value.split(",")

            # Same thing as above, should probably be optional not optionals
            if "optionals" in values:
                values.remove("optionals")
            if "primarykey" in values:
                values.remove("primarykey")

            if values[0] == "array":
                add_entity_attribute(entity, key, DATA_TYPES[values[1]])
            elif values[0] not in RELATIONSHIPS:
                add_entity_attribute(entity, key, DATA_TYPES[values[0]])

# Parses the given XML's model element and creates our initial root 
def get_model(xml):
    xmldoc = minidom.parse(xml)
    itemlist = xmldoc.getElementsByTagName('model') 
    model = etree.Element("model")
    # should set itemlist[0] equal to a variable so it's clearer what's being used
    # I think you can use iteritems() instead of keys() here to loop over both at the same time `for key, value in first_model.attributes.iteritems():`
    for att in itemlist[0].attributes.keys():
        model.set(att, itemlist[0].attributes[att].value)
    return model

# Main script to parse json, add in appropiate entities, relationships and elements
# Re-writes given XML
def main_script(incoming_json, xml):
    # Should use the python file open context manager: http://preshing.com/20110920/the-python-with-statement-by-example/
    # Probably want some user friendly print statements like "Script starting", "Scripts adding entities", "Scripts finishing", etc
    f = open(incoming_json, "r")
    objects = json.loads(f.read())["objects"]
    f.close()
    model = get_model(xml)
    add_entities(model,objects)
    add_relationships(model, objects)
    add_elements(model, objects)
    
    # print tree
    #print etree.tostring(model, pretty_print = True)

    # write tree
    #tree = etree.ElementTree(model)
    #tree.write(xml, pretty_print=True)

# check user input
# TODO: Should make this an interactive session
# Please enter JSON:
# Check if JSON and if JSON is Valid
# Please enter XML:
# Do some kind of check on the XML?

# We should use a main block here: http://stackoverflow.com/questions/4041238/why-use-def-main
# We should also name this file to be more pythonic - core_data_modeler.py
if len(sys.argv) != 3:
    print "Error, usage: " + sys.argv[0] + " <file.json> <file.xml>" 
else:
    main_script(sys.argv[1], sys.argv[2]) 
