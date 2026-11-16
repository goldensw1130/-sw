import json,pathlib,subprocess,sys
out=pathlib.Path('android-output')
subprocess.run(['adb','install','-r',str(out/'QA-app.apk')],check=True)
subprocess.run(['adb','install','-r',str(out/'QA-test.apk')],check=True)
r=subprocess.run(['adb','shell','am','instrument','-w','com.oreummok.validation/com.oreummok.nativeapp.UITest'],capture_output=True,text=True,timeout=240)
(out/'ui-test.log').write_text(r.stdout+r.stderr)
print(r.stdout)
if r.returncode or 'INSTRUMENTATION_CODE: -1' not in r.stdout or 'INSTRUMENTATION_RESULT: error=' in r.stdout:
    raise SystemExit('Native Android validation failed')
required=['realDeviceCloudApiConnected','businessPdfRendered','workspaceDraftsRetained','freeChatNoTarget','freeChatFollowupHistory','receiptReturnNativeScreen','compactWorkHeader','businessSearchAndClear','competitorOnlyStaffMenu']
for key in required:
    if f'INSTRUMENTATION_RESULT: {key}=true' not in r.stdout:raise SystemExit('Missing check: '+key)
(out/'android-validation.json').write_text(json.dumps({'passed':True,'environment':'Android 35 emulator','checks':required,'liveAuthenticatedAI':'not tested; no user credentials in CI'},indent=2))
subprocess.run(['adb','uninstall','com.oreummok.validation'],check=True)
