#!/usr/bin/env python3
__author__ = "Monica Keith"
__status__ = "Production"
__purpose__ = "Positional arguments"

import argparse

parser = argparse.ArgumentParser()
# If not specified, the type by default is string
parser.add_argument("arg1", help="Description of arg1")
parser.add_argument("arg2", help="This should be an integer and will be squared", type=int)
args = parser.parse_args()

print(args)
print(args.arg1)
print(args.arg2**2)

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

def main():
        netID = None
        piID = None

        argv = sys.argv[1:]
        try:
                opts, args = getopt.getopt(argv, "u:p:h:", ["user=", "pi=", "help="])
        except:
                printHelp()
                exit("Error reading arguments")

        for opt,arg in opts:
                if opt in ["-u", "--user"]:
                        netID = arg
                elif opt in ["-p", "--pi"]:
                        piID = arg
                elif opt in ["h","--help"]:
                        printHelp()
                        exit()

        if netID==None or piID==None:
                printHelp()
                exit("Missing arguments")

	if myldaplib.getUserInfo(netID)["uid"]!="":
                exit(f"User {netID} already has an account. Send the following link that contains information on how to login: https://docs.rcc.mcw.edu/user-guide/access/login/")
