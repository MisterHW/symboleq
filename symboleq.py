#!python3
# see also 
#	https://pyspice.fabrice-salvaire.fr/examples/spice-parser/bootstrap-example.html
#	https://stackoverflow.com/questions/11415570/directory-path-types-with-argparse
#	https://docs.python.org/3/library/argparse.html#name-or-flags

import os
import sys
import re
import argparse

import PySpice
import PySpice.Logging.Logging as Logging
logger = Logging.setup_logging()
# change logging level from "DEUBG" to "INFO" in 
# Pythonxx\Lib\site-packages\PySpice\Config\logging.yml
from PySpice.Spice.Library import SpiceLibrary
from PySpice.Spice.Netlist import Circuit
from PySpice.Spice.Parser import SpiceParser
from PySpice.Unit import *


def init_args(): 
	# <filename> [--format <fmt>]  [--debug] 
	parser = argparse.ArgumentParser(description='Provide a SPICE netlist file and turn it into symbolic equations.')
	parser.add_argument('filename', type=lambda x: x if os.path.isfile(x) else None, help='input file (SPICE netlist)')
	parser.add_argument('-f','--format', type=str, default='default', choices=['default','maxima'], help='select an output format')
	parser.add_argument('-d','--debug', action='store_true', help='enable debug output')
	return parser.parse_args()
	
args = init_args()


def debug_print(*arg):
	if args.debug:
		print(*arg)
	return

	
def result_print(s):
	if args.format == 'maxima':
		s = re.sub(r'I\(V([A-Za-z0-9]+)\)', lambda mo:'I[V'+mo.group(1)+']', s)	
		s = re.sub(r'V\(([0-9]*)\)', lambda mo:'V['+mo.group(1)+']', s)
		s = re.sub(r'V\(([A-Za-z0-9]+)\)', lambda mo:'U['+mo.group(1)+']', s)
		s = re.sub(r'I([A-Za-z0-9]+)', lambda mo:'I['+mo.group(1)+']', s)
		s = re.sub(r'R([A-Za-z0-9]+)', lambda mo:'R['+mo.group(1)+']', s)
		s = re.sub(r'C([A-Za-z0-9]+)', lambda mo:'C['+mo.group(1)+']', s)
		s = re.sub(r'L([A-Za-z0-9]+)', lambda mo:'L['+mo.group(1)+']', s)
	print(s)
	return


def process_netlist(fn):
	parser  = SpiceParser(path=fn)
	circuit = parser.build_circuit()

	debug_print("GND net is ", circuit.gnd)
	debug_print("nodes :")
	nodes = circuit.nodes
	gnd = None
	for node in nodes:
		if str(node.name) != str(circuit.gnd):
			debug_print(node.name)
		else:
			gnd = node 
	if gnd != None:
		# remove gnd element from node set 
		nodes.remove(gnd) 
	return [parser, circuit, nodes, gnd]
	
	
netlist_path = os.path.join(os.path.realpath(os.path.dirname(__file__)), args.filename)	
parser, circuit, nodes, gnd = process_netlist(netlist_path)
		
	
def node_voltage_symbol(nodename):
	global gnd
	sym = ''
	if nodename != gnd.name:
		sym = 'V('+nodename+')'
	return sym
	
		
def current_symbol(node, element,negate = False, prefix='', suffix=''):
	# determine which way around the current source is connected
	# "negate" inverts the sign for use with rhs terms
	i = element.nodes.index(node.name) 
	if (i == 0) ^ bool(negate):
		return '(-' + prefix + element.name + suffix + ')'
	else:
		return prefix + element.name + suffix
		
		
def pin_voltage_symbol(node, element):
	i = element.nodes.index(node.name)
	if i == 0:
		return node_voltage_symbol(str(element.nodes[1]))
	else:
		return node_voltage_symbol(str(element.nodes[0]))
		
		
def resistor_symbol(node, element):
	return element.name
	

def capacitor_symbol(node, element):
	return '(1/(j*omega*' + element.name + '))'
	
	
def inductor_symbol(node, element):
	return '(j*omega*' + element.name + ')'


def get_element_current_terms(node, element):
	handler = {
		'Resistor': lambda node, element : ['(' + pin_voltage_symbol(node, element) + '-' + node_voltage_symbol(node.name) + ')/'+
			resistor_symbol(node, element), ''],
		'BehavioralCapacitor': lambda node, element: ['(' + pin_voltage_symbol(node, element) + '-' + node_voltage_symbol(node.name) + ')/'+
			capacitor_symbol(node, element), ''],
		'BehavioralInductor': lambda node, element : ['(' + pin_voltage_symbol(node, element) + '-' + node_voltage_symbol(node.name) + ')/'+
			inductor_symbol(node, element), ''],
		'CurrentSource': lambda node, element : ['',current_symbol(node, element, True)],
		'VoltageSource': lambda node, element : ['',current_symbol(node, element, False, 'I(',')')],
		'default' : lambda node, element : ['[unknown]','']
	}
	if element.__class__.__name__ in handler:
		return handler[element.__class__.__name__](node,element)
	else:
		return handler['default'](node,element)
		

def get_element_voltage_terms(node, element):
	sides = ['','']
	if element.__class__.__name__ == 'VoltageSource':
		# case 1, 2: output terminal of voltage source connected to current node net
		if str(node.name) == str(element.nodes[1]):
			sides[0] = node_voltage_symbol(node.name)
			if str(element.nodes[0]) != str(gnd.name):
				sides[0] = sides[0] + ' - ' + node_voltage_symbol(element.nodes[0])
			sides[1] = '(-V('+element.name+'))'
		# case 3 : return terminal of voltage source connected to node net, output terminal connected to gnd
		#          this will only show up once because the gnd node is not processed
		if (str(node.name) == str(element.nodes[0])) and (str(gnd.name) == str(element.nodes[1])):
			sides[0] = node_voltage_symbol(node.name)
			sides[1] = 'V('+element.name+')'
	return sides 
		
		
def generate_equations(termfunc, accumulate = True):
	global nodes 

	debug_print()
	
	for node in nodes:
		debug_print("node ", node.name)
		elements = node.elements
		debug_print(elements)
		lhs = ''
		rhs = ''
		for e in elements:
			# element_params = e._positional_parameters
			# e.__dict__.keys()
			debug_print(e.name, " : ", e.nodes, " : ", e.__class__.__name__)
			lhst, rhst = termfunc(node, e)
			if lhst != '':
				if lhs != '':
					lhs = lhs + ' + '
				lhs = lhs + lhst
			if rhst != '':
				if rhs != '':
					rhs = rhs + ' + '
				rhs = rhs + rhst
				
			if not accumulate:
				if lhs == '':
					lhs = '0'
				if rhs == '':
					rhs = '0'
				eqn = lhs + ' = ' + rhs
				lhs = ''
				rhs = ''
				if eqn != '0 = 0':
					result_print(eqn)
				continue

		if lhs == '' and rhs == '':
			debug_print('no more equations for node\n')
			continue
			
		if lhs == '':
			lhs = '0'
		if rhs == '':
			rhs = '0'
		eqn = lhs + ' = ' + rhs
		if eqn != '0 = 0':
			result_print(eqn)
		debug_print()
	
	
# for each node: generate KCL equation based on R, I, C, L
generate_equations(get_element_current_terms)
# for each voltage source V: generate additional constraint equations 
generate_equations(get_element_voltage_terms, accumulate=False)
	


		

