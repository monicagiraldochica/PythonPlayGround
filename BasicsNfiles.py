#!/usr/bin/env python3
__author__ = "Monica Keith"
__status__ = "Production"

import externalFunction1
import os
#from os import path

def functboolean():
    print("a"=="b" and "a"!="b")
    print("a"=="b" or "a"!="b")
    print("a"<"b")
    print(not "a"<"b")
    # value_when_true if condition else value_when_false

def functstrings():
    x="hola"
    y="monica"
    z="hola como estas"
    print(x in z)
    print(y in z)
    print(y not in z)
    print(x==y)
    print(x=="hola")
    inputvar = str(raw_input())
    #inputvar = str(input())
    print("Input: "+inputvar)
    print(x==inputvar)

def runShell():
	#import subprocess
	subprocess.run(["ls", "-l"])
	process = subprocess.Popen(['echo', 'More output'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	stdout, stderr = process.communicate()
	print(stdout)
	print(stderr)
	# import os
	os.system('ls -l')
	stream = os.popen('echo returned output')
	output = stream.read()
	output

def getStdOut(command):
        try:
                result = subprocess.run(command, capture_output=True, text=True, check=True)
                return [result.stdout.replace("\n",""),result.stderr.replace("\n","")]

        except subprocess.CalledProcessError as e:
                 return ["",""]

def getStdOut(command):
        try:
                result = subprocess.run(command, capture_output=True, text=True, check=True)
                return [result.stdout,result.stderr]

        except subprocess.CalledProcessError as e:
                 print(f"Error executing command: {e}")
                 return ["",""]

print(getStdOut(["id", "mkeith"]))

def concatstrings():
    x="hola"
    y="monica"
    print(x+y)
    print(x+" "+y)

def modifystrings():
    x=" some string string "
    y=x.strip() # Also deletes trailing/leading tabs and new lines
    print("-"+y+"-")
    y=x.rstrip()
    print("-"+y+"-")
    y=x.lstrip()
    print("-"+y+"-")
    print(x.replace("string","food"))

def scapecharacters():
    x="hola\tmonica\nhola\tmaria\\n"
    print(x)

def funcstringarrays():
    samplelist=["a","h","e","d","c","f","g","b"]
    print(samplelist)
    samplelist.extend([2,3])
    print(samplelist)
    
    #print(dir(samplelist))
    #samplelist.sort() #sorted(samplelist) would sort it temporarily
    #print(samplelist)
    #samplelist.reverse() #to reverse temporarily numberlist[::-1]
    #print(samplelist)
    #print(len(samplelist))
    
    #print(samplelist[0])
    #print(samplelist[-1]) # negative nums access in reverse
    #a=7
    # no incluye el ultimo
    #print(samplelist[1:a])
    #print(samplelist[1:a:2])
    #print(samplelist[1:a:3])
    #print(samplelist[1:a]+["m"])
    #samplelist[1]="mod"
    #print(samplelist)
    #samplelist+=["k"]
    #print(samplelist)
    #del samplelist[0]
    #print(samplelist)
    #del samplelist[list=="d"] # or samplelist.remove("a")
    #print(samplelist)

def funcnumarrays():
    a=[1,2,3,4]
    print(sum(a))
    print(a)
    a.extend([5,6,7,8])
    print(a)

    import numpy as np
    a = np.arrange(12).reshape((3,4))
    print(a)
    [[ 0 1 2 3]
     [ 4 5 6 7]
     [8 9 10 11]]
    mask = np.isnan(array)
    array = np.delete(array,mask)

def funcloops():
    a=[1,2,3,4]
    print(range(len(a)))
    
    iterator=iter(a)
    for i in range(len(a)):
        print(next(iterator))

    #for i in iterator:
    #try:
        # Do something.
        #pass
    #except:
        # Continue to next iteration.
        #continue

# Dictionaries are similar to hashtables
def funcdictionaries():
    #to start it empty dic={}
    dic={"username":"monica", "password":"secret", "age":33}
    print(dic["username"])
    dic["gender"]="female"
    print(dic["gender"])
    del dic["password"]
    print(dic)

    for key,value in dic.items():
        print(key+":"+str(value))
        
    # List of keys:
    # list(dic.keys())
    # List of values:
    # list(dic.values())
        
# Reading CSV files
def pandas():
	#import pandas
	f = "/Volumes/MyExternalHD/OneDrive - Universitat de Barcelona/ResearchProjects/MCW/BinderLab/Fernandino/RAC/SM_localizers_s102_r1.csv"
	# Store the data from the CSV file in a DataFrame
	df = pandas.read_csv(f)
	# Process each line of the file
	# The line will be a series object
	for index,line in df.iterrows():
		print(index)
		print(line)
		print(line["Age"])
	
	for col in np.array(df.columns):
        	print(col)
	
    # Initialize the df with two empty cols and an index col
	df = pd.DataFrame()
    df['sess'] = []
    df['grp'] = []
    df['site'] = []
    df.set_index('sess',inplace=True)
 
    df_cols = df.columns.values.tolist()
    df.columns = ["autokey","sess","image","criteria","pipe"]
    df.index.values.tolist()
    
    grp_col = df['grp'].values.tolist()
    
    # Add entries to the df
    df.loc['EC1114_1','grp'] = 'CON'
    df.loc['EC1115_1','grp'] = 'EPI'
    
    # Tell it that the index is not given by the row number but by the column titled Block
    df = pandas.read_csv(f, index_col='Block')
	print(df)
	#header=1 to skip first line and make header the second line
	#header=None if no header
	
	rts=df.iloc[:,3].values
	M=statistics.mean(rts)
	S=statistics.stdev(rts)
	
	df = pd.read_csv("/group/jbinder/ECP/docs/TLE_GeneralData.txt", sep='\t', index_col="SubjID")
	print(df.loc["EC1007"]) # prints the object EC1007 with the values for each column
	print(df.loc["EC1007","Age"]) # get the age for EC1007
 
    # Save a pandas df in a sheet in an excel file
    import pandas as pd
    writer = pd.ExcelWriter('yourfile.xlsx', engine='xlsxwriter')
    df = pd.read_csv('originalfile.csv')
    df.to_excel(writer, sheet_name='sheetname')
    writer.save()
    
    # Create new column base on condition
    df_file["include"] = list(map(lambda index: index in df_table[new_index].values.tolist(),df_file[new_index].values.tolist()))
    # Drop columns
    df.drop(columns=cols,axis=1,inplace=True)
    
    excel = "...xlsx"
df = pandas.read_excel(excel,names=["NRAnat3_ID","USE_NRAnat3_exam","Exams_AcquisitionDate","neuroreader_date","EMRN","accession_number","neuropsych_test"],index_col=0,usecols="C,F,H,J:M")

    cursor.execute("select sess,scan_date from sessions where sbjID='"+sbjID+"' and scan_date is not null")
    records = cursor.fetchall()
    if len(records)>0:
        df = pd.DataFrame(records)

def functesting():
    #while(input()!=userAge):
        #print("try again")

#    userInput=input()
#    while(userInput!=userAge):
#        print("try again, you typed: "+str(userInput))
#        if(userInput==20):
#            print("oops")
#            break
#        userInput=input()

    while(True):
        inputvar=str(raw_input())
        if(inputvar=="end"):
            break
        if(inputvar=="pass"):
            continue
        print("input: "+inputvar)

def funcexceptions():
    try:
        a=1
        b="2"
        c=a+b
    except:
        print("there was an exception")
    print("continue code")

def funclasses():
    s1=person("monica",33)
    print(s1.age)
    s1.getCountry()
    s1.age=40
    print(s1.age)
    s1.addFriend("jose")
    s1.addFriend("jesus")
    print(s1.friends)
    del s1 #delete object

    p1=student("maria",27)
    print(p1.age)
    p1.setAge(44)
    print(p1.age)
    p1.getCountry()
    p1.somefunc()

def funcFiles(selection,mode):
	#num_lines=sum(1 for line in file)
	#num_lines=sum(1 for line in open('filename.txt'))
    if(selection=="csv"):
        file1=open("/Volumes/MyExternalHD/Rockland/AssessmentData/8100_ANT_20160809.csv")
        print("name: "+file1.name+" mode: "+file1.mode)
        if(mode=="all"):
            print(file1.read())
        elif(mode=="nlines"):
            print(file1.readline())
            print(file1.readline())
        elif(mode=="loop"):
            for line in file1:
                print(line)
        file1.close()
    elif(selection=="txt"):
        file2=open("/Volumes/MyExternalHD/Rockland/list_all.txt","r") #r=read only (default),r+=read&write,a=append,a+=read&append,w=overwrite(pointer to 0),w+=read&overwrite,b=binary,rb=read binary,x=just creates a file but a & 3 also create a file
        print("name: "+file2.name+" mode: "+file2.mode)
        if(mode=="all"):
            print(file2.read())
        elif(mode=="nlines"):
            print("pointer: "+str(file2.tell()))
            file2.seek(10) #skip 10 characters (from the beginning of file, same as 2nd parameter 0)
            print(file2.readline())
            file2.seek(10,0) #same as before, repeats previous line because im repositioning at character 10 of the file
            print(file2.readline())
            file2.seek(10,1) #skip relative to where the pointer currently is
            print(file2.readline())
        elif(mode=="loop"):
            for line in file2:
                print(line)
        file2.close()
    elif(selection=="write"):
        file3=open("/Volumes/MyExternalHD/PersonalDrive/Scripts/PythonScripts/Learning/test.txt","r+")
        print(file3.read())
        file3.write("text") #wrote at the end
        print(file3.read())
        file3.seek(0)
        file3.write("Hola") #overwrote at the beginning
        file3.close()
        file3=open("/Volumes/MyExternalHD/PersonalDrive/Scripts/PythonScripts/Learning/test.txt","a")
        file3.write("\nBye") #wrote at the end
        file3=open("/Volumes/MyExternalHD/PersonalDrive/Scripts/PythonScripts/Learning/test.txt","w")
        file3.write("Hello Word") #overwrote the whole file
        #os.remove("/Volumes/MyExternalHD/PersonalDrive/Scripts/PythonScripts/Learning/test.txt")
        #os.rmdir("...") you can only remove empty folders
        print(str(os.path.exists("/Volumes/MyExternalHD/PersonalDrive/Scripts/PythonScripts/Learning/test.txt")))
        #print(file.read(5)) reads the first 5 characters of the file

class person(object):
    country="colombia" #shared by all students
    def __init__(self, name, age):
        self.name = name
        self.age = age
        self.friends = [] #create a new empty list
    def getCountry(self):
        print(self.country)
    def addFriend(self,friend):
        self.friends.append(friend)
    def setAge(self,age):
        self.age = age
    def somefunc(self):
        print("original print")

class student(person):
    id="9090"
    def getCountry(self):
        print("there's no country")
    def somefunc(self):
        super(student,self).somefunc()
        print("some extra print")

#externalFunction1.func1()
funcFiles("write","")
print("Present, ", end =" ") # to end the line with a space instead of \n
