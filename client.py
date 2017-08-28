from urllib.request import urlopen

r_fail = urlopen(url='https://ili-file-service.herokuapp.com/?https://gnps.ucsd.edu/ProteoSAFe/DownloadResultFile?task=b6e2d606b1ca4f3d9262652b2c37f1ca&block=main&file=ili_stl_model/ili_stl_model-00000.stl')
r_ok = urlopen(url='https://ili-file-service.herokuapp.com/?https://gnps.ucsd.edu/ProteoSAFe/DownloadResultFile?task=b6e2d606b1ca4f3d9262652b2c37f1ca&block=main&file=ili_output/ba890b74e5c64036bcd37681ab64d502.csv')
r_mbl = urlopen(url='http://www.ebi.ac.uk/metabolights/MTBLS334/files/1C%20Obese.raw')
print(r_ok.headers)
print('======================')
print(r_fail.headers)
print('======================')
print(r_mbl.headers)
