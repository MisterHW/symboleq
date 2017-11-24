#!python3
# see also https://pyspice.fabrice-salvaire.fr/examples/spice-parser/bootstrap-example.html

import os
import sys

if len(sys.argv) != 2:
	print('This script must be called with exactly one filename. usage:\r\n\tsymboleq.py "<spice netlist file>"')
	exit(0)
fn = sys.argv[1]

netlist_path = os.path.join(os.path.realpath(os.path.dirname(__file__)), fn)


import PySpice
import PySpice.Logging.Logging as Logging
logger = Logging.setup_logging()
# change logging level from "DEUBG" to "INFO" in 
# Pythonxx\Lib\site-packages\PySpice\Config\logging.yml
from PySpice.Spice.Library import SpiceLibrary
from PySpice.Spice.Netlist import Circuit
from PySpice.Spice.Parser import SpiceParser
from PySpice.Unit import *


def debug_print(*arg):
	#print(*arg)
	return

def result_print(*arg):
	print(*arg)
	return


parser = SpiceParser(path=netlist_path)
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
	nodes.remove(gnd) # remove gnd element from node set 
		
		


def node_voltage_symbol(nodename):
	global gnd
	sym = ''
	if nodename != gnd.name:
		sym = 'V('+nodename+')'
	return sym
	
		
def current_symbol(node, element):
	i = element.nodes.index(node.name)
	if i == 0:
		return '(-'+element.name+')'
	else:
		return element.name
		
		
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
		'Capacitor': node, element : ['(' + pin_voltage_symbol(node, element) + '-' + node_voltage_symbol(node.name) + ')/'+
			capacitor_symbol(node, element), ''],
		'Inductor': node, element : ['(' + pin_voltage_symbol(node, element) + '-' + node_voltage_symbol(node.name) + ')/'+
			inductor_symbol(node, element), ''],
		'CurrentSource': lambda node, element : ['',current_symbol(node, element)],
		'VoltageSource': lambda node, element : ['', ''],
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
			sides[1] = 'V('+element.name+')'
		# case 3 : return terminal of voltage source connected to node net, output terminal connected to gnd
		#          this will only show up once because the gnd node is not processed
		if (str(node.name) == str(element.nodes[0])) and (str(gnd.name) == str(element.nodes[1])):
			sides[0] = node_voltage_symbol(node.name)
			sides[1] = '(-V('+element.name+'))'
	return sides 
		
		
def generate_equations(termfunc, accumulate = True):
	global nodes 

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
	


		

