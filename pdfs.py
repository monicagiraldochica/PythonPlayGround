#!/usr/bin/env python3
__author__ = "Monica Keith"
__status__ = "Production"
__purpose__ = "Manipulate PDFs"

from PyPDF2 import PdfFileReader, PdfFileWriter
import os

def getfields(ped_path):
	# https://pythonhosted.org/PyPDF2/PdfFileReader.html
	
	f=open(pdf_path,'rb')
	pdf=PdfFileReader(f)

	info=pdf.getDocumentInfo()
	title=info.title
	author=info.author
	creator=info.creator
	producer=info.producer
	nPages=pdf.getNumPages()

	if title!=None:
		print("Title: "+title)
	if author!=None:
		print("Author: "+author)
	if creator!=None:
		print("Creator: "+creator)
	if producer!=None:
		print("Producer: "+producer)
	print("# pages: "+str(nPages))

	# getFormTextFields() gives in this case the same as the getFields()
	fields=pdf.getFields()
	for field,subfield in fields.items():
		print(field)
		for key,val in subfield.items():
			if key=="/V":
				print(val) 

def getoutline(pdf_path):
	f=open(pdf_path,'rb')
	pdf=PdfFileReader(f)
	outline=pdf.getOutlines()
	print(outline)

def getmetadata(pdf_path):
	f=open(pdf_path,'rb')
	pdf=PdfFileReader(f)
	metadata=pdf.getXmpMetadata()
	print("Date created: "+str(metadata.xmp_createDate))
	print("Date modified: "+str(metadata.xmp_modifyDate))
	print("Creator: "+str(metadata.dc_creator[0]))
	# https://pythonhosted.org/PyPDF2/XmpInformation.html

def isencrypted(pdf_path):
	f=open(pdf_path,'rb')
	pdf=PdfFileReader(f)
	if pdf.isEncrypted:
		print("is encripted")
	else:
		print("is not encripted")

def decrypt_pdf(encr_file):
	encf=open(encr_file,'rb')
	encpdf=PdfFileReader(encf)
	if encpdf.isEncrypted:
		print("Do you know the password? (Y/N)")
		ans=str(input())
		if ans=='Y':
			ok=encpdf.decrypt("password")
			if ok==0:
				print("Wrong password")
		else:
			print("Goodbye")

def rotate_pages(pdf_path):
    pdf_writer = PdfFileWriter()
    pdf_reader = PdfFileReader(pdf_path)
    # Rotate page 90 degrees to the right
    page_1 = pdf_reader.getPage(0).rotateClockwise(90)
    pdf_writer.addPage(page_1)
    # Rotate page 90 degrees to the left
    page_2 = pdf_reader.getPage(1).rotateCounterClockwise(90)
    pdf_writer.addPage(page_2)
    # Add a page in normal orientation
    pdf_writer.addPage(pdf_reader.getPage(2))

    with open('rotate_pages.pdf', 'wb') as fh:
        pdf_writer.write(fh)
        
def merge_pdfs(paths, output):
    pdf_writer = PdfFileWriter()

    for path in paths:
        pdf_reader = PdfFileReader(path)
        for page in range(pdf_reader.getNumPages()):
            # Add each page to the writer object
            pdf_writer.addPage(pdf_reader.getPage(page))

    # Write out the merged PDF
    with open(output, 'wb') as out:
        pdf_writer.write(out)

def split(path, name_of_split):
    pdf = PdfFileReader(path)
    for page in range(pdf.getNumPages()):
        pdf_writer = PdfFileWriter()
        pdf_writer.addPage(pdf.getPage(page))

        output = name_of_split+page+".pdf"
        with open(output, 'wb') as output_pdf:
            pdf_writer.write(output_pdf)
            
def create_watermark(input_pdf, output, watermark):
    watermark_obj = PdfFileReader(watermark)
    watermark_page = watermark_obj.getPage(0)

    pdf_reader = PdfFileReader(input_pdf)
    pdf_writer = PdfFileWriter()

    # Watermark all the pages
    for page in range(pdf_reader.getNumPages()):
        page = pdf_reader.getPage(page)
        # overlay the watermark_page on top of the current page
        page.mergePage(watermark_page)
        pdf_writer.addPage(page)

    with open(output, 'wb') as out:
        pdf_writer.write(out)
        
# an owner password will basically give you administrator privileges over the PDF and allow you to set permissions on the document. On the other hand, the user password just allows you to open the document
def add_encryption(input_pdf, output_pdf, password):
    pdf_writer = PdfFileWriter()
    pdf_reader = PdfFileReader(input_pdf)

	# Since you will want to encrypt the entire input PDF, you will need to loop over all of its pages and add them to the writer.
    for page in range(pdf_reader.getNumPages()):
        pdf_writer.addPage(pdf_reader.getPage(page))

	# The default is for 128-bit encryption to be turned on. If you set it to False, then 40-bit encryption will be applied instead.
    pdf_writer.encrypt(user_pwd=password,owner_pwd=None,use_128bit=True)

    with open(output_pdf, 'wb') as fh:
        pdf_writer.write(fh)

if __name__ == '__main__':
	os.chdir("/Volumes/MyExternalHD/OneDrive - Universitat de Barcelona/Condos/3dWar")
	input="Mail.pdf"
    	output="Mail-enc.pdf"
    	add_encryption(input_pdf=input,output_pdf=output,password='something')
	# CONTINUE HERE:
	# 1. See if password can be passed as a parameter (it was failing)
	# 2. Try iterating trhough the pdfs of a folder and encypting if they're not encrypted
	# 3. Try encrypting the whole pdf instead of page by page
	# 4. Ask for password input user
	# 5. Do in all files I want
	
	#getfields("/Volumes/MyExternalHD/OneDrive - Universitat de Barcelona/PersonalDocs/Immigration/USA/GreenCardApplication/EAD2019/g-1145edited.pdf")
	#decrypt_pdf("/Volumes/MyExternalHD/OneDrive - Universitat de Barcelona/PersonalDocs/Immigration/USA/GreenCardApplication/newFormsAfterSubmission/i-864.pdf")
    	#paths = ['document1.pdf', 'document2.pdf']
    	#merge_pdfs(paths, output='merged.pdf')
    	#path = 'Jupyter_Notebook_An_Introduction.pdf'
    	#split(path, 'jupyter_page')
	#create_watermark(input_pdf='Jupyter_Notebook_An_Introduction.pdf',output='watermarked_notebook.pdf',watermark='watermark.pdf')
    
# look at documentation of the PdfFileWriter (& reader?)
# About pdf security: paper on the topic
# https://pythonhosted.org/PyPDF2/
# https://github.com/claird/PyPDF4
# https://github.com/pmaupin/pdfrw
# https://www.reportlab.com/
# https://github.com/euske/pdfminer
# https://github.com/socialcopsdev/camelot
