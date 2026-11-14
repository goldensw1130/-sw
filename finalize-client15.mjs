import fs from 'node:fs';
let p='native/desktop/AssistantWorkspace.cs',s=fs.readFileSync(p,'utf8');s=s.replace('args["consent"]=true;','args["consent"]=true;args["previewToken"]=J.Text(reviewed,"previewToken");');fs.writeFileSync(p,s);
p='native/android/MainActivity.java';s=fs.readFileSync(p,'utf8');s=s.replace('args.put("preview",reviewed[0].getJSONObject("context").toString());','args.put("previewToken",reviewed[0].getString("previewToken"));');fs.writeFileSync(p,s);
