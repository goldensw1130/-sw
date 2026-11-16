"""Build the production unsigned APK and a separate ephemeral QA-signed test pair.
The production signing key is never supplied to CI.
"""
import hashlib,json,os,pathlib,shutil,subprocess,urllib.request,zipfile
ROOT=pathlib.Path(__file__).resolve().parent.parent
SDK=pathlib.Path(os.environ['ANDROID_HOME'])
BT=SDK/'build-tools'/'34.0.0'
JAR=SDK/'platforms'/'android-35'/'android.jar'
SRC=ROOT/'native-client-source'/'android'
BUILD=ROOT/'android-build'
OUT=ROOT/'android-output'
VERSION=json.loads((ROOT/'release.json').read_text())['version']
def run(*args): subprocess.run([str(x) for x in args],check=True,cwd=ROOT)
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
for p in [BUILD/'res'/'drawable',BUILD/'assets'/'fonts',BUILD/'classes',BUILD/'dex',OUT]: p.mkdir(parents=True,exist_ok=True)
shutil.copy2(ROOT/'assets'/'brand'/'app-icon.png',BUILD/'res'/'drawable'/'icon.png')
if digest(BUILD/'res'/'drawable'/'icon.png')!='5340e9ab55fb707dfa652cd79d6587c2333fad024b0633a306430c29b61f56e2':raise RuntimeError('Brand icon checksum mismatch')
spec=json.loads((ROOT/'assets'/'fonts'/'SOURCE.json').read_text())
for name,sha in spec['files'].items():
    p=BUILD/'assets'/'fonts'/name
    urllib.request.urlretrieve('https://raw.githubusercontent.com/google/fonts/main/ofl/gothica1/'+name,p)
    if digest(p)!=sha: raise RuntimeError('Font checksum mismatch: '+name)
run(BT/'aapt','package','-f','-A',BUILD/'assets','-M',SRC/'AndroidManifest.xml','-S',BUILD/'res','-I',JAR,'-F',BUILD/'resources.apk')
run('javac','-encoding','UTF-8','-source','8','-target','8','-classpath',JAR,'-d',BUILD/'classes',*[SRC/n for n in ['MainActivity.java','StairCanvas.java','SecureLogin.java','BusinessPdf.java','BrandHeader.java','ApiKeyInput.java']])
run('jar','cf',BUILD/'classes.jar','-C',BUILD/'classes','.')
run('java','-cp',BT/'lib'/'d8.jar','com.android.tools.r8.D8','--lib',JAR,'--min-api','26','--output',BUILD/'dex',BUILD/'classes.jar')
shutil.copy2(BUILD/'resources.apk',BUILD/'unsigned.apk')
with zipfile.ZipFile(BUILD/'unsigned.apk','a',zipfile.ZIP_DEFLATED) as z:z.write(BUILD/'dex'/'classes.dex','classes.dex')
unsigned=OUT/f'OreumMok-Android-v{VERSION}-unsigned.apk'
run(BT/'zipalign','-f','4',BUILD/'unsigned.apk',unsigned)
shutil.copy2(BT/'lib'/'apksigner.jar',OUT/'apksigner.jar')
os.environ['OREUM_QA_SIGN_PASS']='ephemeral-ci-only-not-production'
key=BUILD/'qa.keystore'
run('keytool','-genkeypair','-keystore',key,'-alias','qa','-keyalg','RSA','-keysize','2048','-validity','2','-dname','CN=Ephemeral OreumMok QA','-storepass:env','OREUM_QA_SIGN_PASS','-keypass:env','OREUM_QA_SIGN_PASS')
def sign(source,destination):
    run('java','-jar',BT/'lib'/'apksigner.jar','sign','--ks',key,'--ks-key-alias','qa','--ks-pass','env:OREUM_QA_SIGN_PASS','--key-pass','env:OREUM_QA_SIGN_PASS','--out',destination,source)
sign(unsigned,OUT/'QA-app.apk')
testdir=BUILD/'test'
for p in [testdir,testdir/'classes',testdir/'dex']:p.mkdir(exist_ok=True)
(testdir/'AndroidManifest.xml').write_text('<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="com.oreummok.validation"><uses-sdk android:minSdkVersion="26" android:targetSdkVersion="35"/><application android:label="Temporary validation"/><instrumentation android:name="com.oreummok.nativeapp.UITest" android:targetPackage="com.oreummok.nativeapp"/></manifest>')
run('node',ROOT/'native-client-source'/'write-business-fixture.mjs',testdir/'BusinessFixture.java')
run(BT/'aapt','package','-f','-M',testdir/'AndroidManifest.xml','-I',JAR,'-F',testdir/'resources.apk')
run('javac','-encoding','UTF-8','-source','8','-target','8','-classpath',JAR,'-d',testdir/'classes',SRC/'validation'/'UITest.java',testdir/'BusinessFixture.java')
run('jar','cf',testdir/'classes.jar','-C',testdir/'classes','.')
run('java','-cp',BT/'lib'/'d8.jar','com.android.tools.r8.D8','--lib',JAR,'--min-api','26','--output',testdir/'dex',testdir/'classes.jar')
shutil.copy2(testdir/'resources.apk',testdir/'unsigned.apk')
with zipfile.ZipFile(testdir/'unsigned.apk','a',zipfile.ZIP_DEFLATED) as z:z.write(testdir/'dex'/'classes.dex','classes.dex')
run(BT/'zipalign','-f','4',testdir/'unsigned.apk',testdir/'aligned.apk')
sign(testdir/'aligned.apk',OUT/'QA-test.apk')
with zipfile.ZipFile(unsigned) as z:
    hashes={n:hashlib.sha256(z.read(n)).hexdigest() for n in ['classes.dex','resources.arsc','AndroidManifest.xml']}
(OUT/'code-checksums.json').write_text(json.dumps({'version':VERSION,'unsignedSha256':digest(unsigned),'entries':hashes},indent=2))
print(json.dumps({'built':True,'version':VERSION,'productionKeyUsed':False}))
