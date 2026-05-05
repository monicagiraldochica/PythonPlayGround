#!/usr/bin/env python3
__author__ = "Monica Keith"
__status__ = "Production"
__purpose__ = "Positional arguments"

def fununknownargs2(name,*args):
    for item in args:
        print(name+": "+str(item))

def print_kwargs(**kwargs):
    print(kwargs)
    for key,value in kwargs.items():
        print(key)
        print(value)
        print(str(key)+": "+str(value))
        print("The value of {} is {}".format(key, value))
        print("%s %s" %(key,value))

# GET NUMBER OF ARGUMENTS AND FIRST ARGUMENT
import sys
if len(sys.argv)!=2:
	sys.exit("Wrong number of arguments")
subject=sys.argv[1]

print_kwargs(kwargs_1="Shark", kwargs_2=4.5, kwargs_3=True)