#!/usr/bin/env python3
__author__ = "Monica Keith"
__status__ = "Production"

import requests

def is_downloadable(url):
    """
        Does the url contain a downloadable resource
        """
    h = requests.head(url, allow_redirects=True)
    header = h.headers
    content_type = header.get('content-type')
    if 'text' in content_type.lower():
        return False
    if 'html' in content_type.lower():
        return False
    return True

def examples1():
    print('Beginning file download with urllib2 Module')
    filedata = urllib2.urlopen('http://i3.ytimg.com/vi/J---aiyznGQ/mqdefault.jpg')
    datatowrite = filedata.read()
    # wb: write in binary mode (for files that are not supposed to be text files)
    with open('/Volumes/MyExternalHD/PersonalDrive/Scripts/PythonScripts/Learning/cat2.jpg', 'wb') as f:
        f.write(datatowrite)

    print('Beginning file download with requests')
    url = 'http://i3.ytimg.com/vi/J---aiyznGQ/mqdefault.jpg'
    # r is a responce object
    r = requests.get(url)
    with open('/Volumes/MyExternalHD/PersonalDrive/Scripts/PythonScripts/Learning/cat3.jpg', 'wb') as f:
        f.write(r.content)
    # Retrieve HTTP meta-data
    print(r.status_code)
    print(r.headers['content-type'])
    print(r.encoding)

    print('Beginning file download with wget module')
    url = 'http://i3.ytimg.com/vi/J---aiyznGQ/mqdefault.jpg'
    wget.download(url, '/Volumes/MyExternalHD/PersonalDrive/Scripts/PythonScripts/Learning/cat4.jpg')

    print is_downloadable('https://www.youtube.com/watch?v=9bZkp7q19f0')
    # >> False
    print is_downloadable('http://google.com/favicon.ico')
    # >> True

def examples2():
    # httpbin.org/post?key=value
    r = requests.post('https://httpbin.org/post', data = {'key':'value'})
    r = requests.put('https://httpbin.org/put', data = {'key':'value'})
    r = requests.delete('https://httpbin.org/delete')
    r = requests.head('https://httpbin.org/get')
    r = requests.options('https://httpbin.org/get')
    # if you wanted to pass key1=value1 and key2=value2 to httpbin.org/get
    payload = {'key1': 'value1', 'key2': 'value2'}
    r = requests.get('https://httpbin.org/get', params=payload)
    # You can see that the URL has been correctly encoded by printing the URL
    print(r.url)
    # You can also pass a list of items as a value
    payload = {'key1': 'value1', 'key2': ['value2', 'value3']}
    r = requests.get('https://httpbin.org/get', params=payload)
    print(r.url)
    print(r.text)
    r = requests.get('https://api.github.com/events')
    r.json()
    r.raise_for_status()
    print(r.status_code)
    print(r.status_code == requests.codes.ok)
    url = 'https://api.github.com/some/endpoint'
    headers = {'user-agent': 'my-app/0.0.1'}
    r = requests.get(url, headers=headers)

def examples3():
    # Redirection and History
    #The Response.history list contains the Response objects that were created in order to complete the request. The list is sorted from the oldest to the most recent response.
    r = requests.get('http://github.com/')
    print(r.url)
    print(r.status_code)
    print(r.history)
    r = requests.get('http://github.com/', allow_redirects=False)
    print(r.status_code)
    print(r.history)
    r = requests.head('http://github.com/', allow_redirects=True)
    print(r.status_code)
    print(r.history)

def xnatdownload(xnat_folder_p,id_p,username='mkeith',password='Hola123.'):
    # curl --keepalive-time 10 -X GET -u mkeith:Hola123. cirxnat1.rcc.mcw.edu:8080/xnat/data/archive/projects/Head2Head2/subjects/01010114/experiments/PC_1_A_01010114/reconstructions/Head2Head2_PC_1_A_01010114_DWIPreprocessing/files/Head2Head2_PC_1_A_01010114_DWIPreprocessing_SB_DTI_MCW_AP__nat__other__FINAL_DTI_PREPROCESS__all__0__v3.nii.gz -o ./PC_1_A_01010114/bedpostx/data.nii.gz
    num=(id_p.split('_'))[3]
    url='http://cirxnat1.rcc.mcw.edu:8080'+xnat_folder_p+'/'+num+'/experiments/'+id_p+'/reconstructions/Head2Head2_'+id_p+'_DWIPreprocessing/files/Head2Head2_'+id_p+'_DWIPreprocessing_SB_DTI_MCW_AP__nat__other__FINAL_DTI_PREPROCESS__all__0__v3.nii.gz'
    r = requests.get(url, auth=(username,password))
    with open('/Volumes/MyExternalHD/PersonalDrive/Scripts/PythonScripts/Learning/data.nii.gz', 'wb') as f:
        f.write(r.content)

xnat_folder='/xnat/data/archive/projects/Head2Head2/subjects'
id='PC_1_A_01010114'
xnatdownload(xnat_folder,id)
