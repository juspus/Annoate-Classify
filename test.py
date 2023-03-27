import numpy
import sys
import getopt
import importlib
from os import listdir
from os.path import isfile, join

def main(argv):
   inputfile = ''
   outputfile = ''
   try:
      opts, args = getopt.getopt(argv,"hi:o:a:",["ifile=","aagent="])
   except getopt.GetoptError:
      print("test.py -i <inputfile> -o <outputfile>")
      sys.exit(2)
   for opt, arg in opts:
      if opt == '-h':
         print("test.py -i <inputfile> -a <agent>")
         sys.exit()
      elif opt in ("-i", "--ifile"):
         inputfile = arg
      elif opt in ("-a", "--aagent"):
         outputfile = arg
   #print("Input file is " + inputfile)
   print(outputfile)

if __name__ == "__main__":
   main(sys.argv[1:])
   pathToPlugins = "Plugins/"
   onlyfiles = [f for f in listdir(pathToPlugins) if isfile(join(mypath, f))]
