using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
using System.Text.RegularExpressions;
using System.Web.Script.Serialization;
using System.Windows.Forms;

static class NativeInstall {
 static readonly JavaScriptSerializer Json=new JavaScriptSerializer{MaxJsonLength=4000000};
 static string Version {get{return Assembly.GetExecutingAssembly().GetName().Version.ToString(3);}}
 static string Hash(string file){using(var h=SHA256.Create())using(var s=File.OpenRead(file))return BitConverter.ToString(h.ComputeHash(s)).Replace("-","").ToLowerInvariant();}
 static bool Linked(string path){return (File.GetAttributes(path)&FileAttributes.ReparsePoint)!=0;}
 static string Inside(string root,string relative){string full=Path.GetFullPath(Path.Combine(root,relative)),prefix=root.TrimEnd(Path.DirectorySeparatorChar)+Path.DirectorySeparatorChar;if(!full.StartsWith(prefix,StringComparison.OrdinalIgnoreCase))throw new IOException("설치 파일 경로 오류");return full;}
 static Dictionary<string,string> Manifest(string root){return Json.Deserialize<Dictionary<string,string>>(File.ReadAllText(Path.Combine(root,"native-checksums.json")));}
 static void Verify(string root){var hashes=Manifest(root);if(hashes==null||hashes.Count==0)throw new IOException("설치 검증 목록이 없습니다.");foreach(var pair in hashes){if(!Regex.IsMatch(pair.Value??"","^[a-fA-F0-9]{64}$")||!File.Exists(Inside(root,pair.Key))||!String.Equals(Hash(Inside(root,pair.Key)),pair.Value,StringComparison.OrdinalIgnoreCase))throw new IOException("설치 파일 검증 실패: "+pair.Key);}}
 static long UserBytes(string root,HashSet<string> owned,string directory){long size=0;foreach(string path in Directory.GetFileSystemEntries(directory)){string rel=path.Substring(root.Length+1);if(rel.Split(Path.DirectorySeparatorChar)[0].Equals("upgrade-backups",StringComparison.OrdinalIgnoreCase))continue;if(Linked(path))throw new IOException("설치 폴더 안의 연결 파일·폴더는 자동 교체할 수 없습니다.");if(Directory.Exists(path))size=checked(size+UserBytes(root,owned,path));else if(!owned.Contains(rel.Replace('\\','/'))&&!rel.Equals("installation-result.json",StringComparison.OrdinalIgnoreCase)&&!rel.Equals("previous-installation.json",StringComparison.OrdinalIgnoreCase))size=checked(size+new FileInfo(path).Length);}return size;}
 static void CheckCollisions(string root,HashSet<string> oldOwned,HashSet<string> newOwned,string directory){foreach(string path in Directory.GetFileSystemEntries(directory)){string rel=path.Substring(root.Length+1).Replace('\\','/');if(rel.Split('/')[0].Equals("upgrade-backups",StringComparison.OrdinalIgnoreCase))continue;if(Linked(path))throw new IOException("설치 폴더 안의 연결 파일·폴더는 자동 교체할 수 없습니다.");if(Directory.Exists(path))CheckCollisions(root,oldOwned,newOwned,path);else if(!oldOwned.Contains(rel)&&newOwned.Contains(rel)&&rel!="installation-result.json"&&rel!="previous-installation.json"&&rel!="native-checksums.json")throw new IOException("기존 사용자 파일과 새 설치 파일의 이름이 같습니다: "+rel);}}
 static void Preserve(string root,string stage,HashSet<string> owned,string directory){foreach(string path in Directory.GetFileSystemEntries(directory)){string rel=path.Substring(root.Length+1);if(rel.Split(Path.DirectorySeparatorChar)[0].Equals("upgrade-backups",StringComparison.OrdinalIgnoreCase))continue;if(Linked(path))throw new IOException("연결 파일·폴더는 자동 복사할 수 없습니다.");if(Directory.Exists(path))Preserve(root,stage,owned,path);else if(!owned.Contains(rel.Replace('\\','/'))&&!rel.Equals("installation-result.json",StringComparison.OrdinalIgnoreCase)&&!rel.Equals("previous-installation.json",StringComparison.OrdinalIgnoreCase)){string dest=Inside(stage,rel);if(File.Exists(dest))throw new IOException("사용자 파일과 설치 파일의 이름이 같습니다: "+rel);Directory.CreateDirectory(Path.GetDirectoryName(dest));File.Copy(path,dest,false);}}}
 static void PrunePrevious(string target,string oldPointer,List<string> warnings){
  if(String.IsNullOrEmpty(oldPointer))return;
  try{string old=Path.GetFullPath(oldPointer);if(!Regex.IsMatch(old.Substring(target.Length),@"^\.backup-[a-f0-9]{32}$")||!old.StartsWith(target+".backup-",StringComparison.OrdinalIgnoreCase)||!Directory.Exists(old)||Linked(old))return;var owned=new HashSet<string>(Manifest(old).Keys.Select(x=>x.Replace('\\','/')),StringComparer.OrdinalIgnoreCase);owned.Add("native-checksums.json");owned.Add("installation-result.json");owned.Add("previous-installation.json");if(UserBytes(old,owned,old)!=0||Directory.Exists(Path.Combine(old,"upgrade-backups"))){warnings.Add("이전 백업에 추가 파일이 있어 자동 정리하지 않았습니다.");return;}Directory.Delete(old,true);}catch{warnings.Add("이전 설치 백업은 수동 확인을 위해 보존했습니다.");}
 }
 public static string Run(string folder,bool shortcut,bool launch){
  string target=Path.GetFullPath(folder).TrimEnd(Path.DirectorySeparatorChar),parent=Path.GetDirectoryName(target);
  if(String.IsNullOrEmpty(parent)||String.Equals(target,Path.GetPathRoot(target).TrimEnd(Path.DirectorySeparatorChar),StringComparison.OrdinalIgnoreCase))throw new IOException("드라이브 루트 대신 오름목 전용 폴더를 선택하세요.");
  bool existing=Directory.Exists(target);if(existing&&(Linked(target)||(Directory.EnumerateFileSystemEntries(target).Any()&&!File.Exists(Path.Combine(target,"native-checksums.json")))))throw new IOException("설치 폴더는 빈 폴더 또는 기존 오름목 전용 폴더여야 합니다.");
  foreach(string name in new[]{"OreumMok","OreumMokUser","node"})foreach(Process p in Process.GetProcessesByName(name)){try{if(Path.GetFullPath(p.MainModule.FileName).StartsWith(target+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase))throw new InvalidOperationException("실행 중인 오름목 창을 닫은 뒤 설치하세요.");}catch(InvalidOperationException){throw;}catch{}}
  string stage=target+".install-"+Guid.NewGuid().ToString("N"),backup=target+".backup-"+Guid.NewGuid().ToString("N"),oldPointer=null;bool movedOld=false,movedNew=false,committed=false;var warnings=new List<string>();
  try {
   if(existing&&File.Exists(Path.Combine(target,"previous-installation.json"))){try{var pointer=Json.Deserialize<Dictionary<string,string>>(File.ReadAllText(Path.Combine(target,"previous-installation.json")));oldPointer=pointer["path"];}catch{}}
   using(Stream embedded=Assembly.GetExecutingAssembly().GetManifestResourceStream("payload.zip"))using(var zip=new ZipArchive(embedded,ZipArchiveMode.Read)){
    long size=0;var paths=new HashSet<string>(StringComparer.OrdinalIgnoreCase);foreach(var entry in zip.Entries){Inside(stage,entry.FullName);if(!paths.Add(entry.FullName.Replace('\\','/')))throw new IOException("중복된 설치 파일 경로가 있습니다.");size=checked(size+entry.Length);}
    var owned=new HashSet<string>(paths,StringComparer.OrdinalIgnoreCase),oldOwned=new HashSet<string>(StringComparer.OrdinalIgnoreCase);if(existing&&File.Exists(Path.Combine(target,"native-checksums.json")))foreach(string key in Manifest(target).Keys){oldOwned.Add(key.Replace('\\','/'));owned.Add(key.Replace('\\','/'));}if(existing)CheckCollisions(target,oldOwned,paths,target);
    long preserve=existing?UserBytes(target,owned,target):0,required=checked(size+preserve+32L*1024*1024),available=new DriveInfo(Path.GetPathRoot(target)).AvailableFreeSpace;
    if(Environment.GetEnvironmentVariable("OREUMMOK_INSTALLER_QA")=="1"&&Environment.GetEnvironmentVariable("OREUMMOK_QA_NO_SPACE")=="1")available=0;
    if(available<required)throw new IOException("설치 공간이 부족합니다. 최소 "+Math.Ceiling(required/1048576d)+"MB, 현재 "+Math.Floor(available/1048576d)+"MB입니다. 기존 설치는 변경하지 않았습니다.");
    Directory.CreateDirectory(stage);foreach(var entry in zip.Entries){string dest=Inside(stage,entry.FullName);if(entry.FullName.EndsWith("/")){Directory.CreateDirectory(dest);continue;}Directory.CreateDirectory(Path.GetDirectoryName(dest));using(var input=entry.Open())using(var output=File.Create(dest))input.CopyTo(output);}
    Verify(stage);var manifest=Manifest(stage);foreach(string entry in paths)if(!entry.EndsWith("/")&&entry!="native-checksums.json"&&!manifest.ContainsKey(entry))throw new IOException("검증 목록에 없는 설치 파일: "+entry);
    if(existing)Preserve(target,stage,owned,target);
   }
   File.WriteAllText(Path.Combine(stage,"installation-result.json"),Json.Serialize(new{version=Version,native=true,verified=true,installed=DateTime.Now.ToString("o"),target=target,transactional=true}));
   if(existing)File.WriteAllText(Path.Combine(stage,"previous-installation.json"),Json.Serialize(new{path=backup}));
   if(existing){Directory.Move(target,backup);movedOld=true;}Directory.Move(stage,target);movedNew=true;
   if(Environment.GetEnvironmentVariable("OREUMMOK_INSTALLER_QA")=="1"&&Environment.GetEnvironmentVariable("OREUMMOK_QA_FAIL_AFTER_SWAP")=="1")throw new IOException("QA simulated failure after swap");
   Verify(target);committed=true;
  } catch {
   if(!committed){if(movedNew&&Directory.Exists(target))Directory.Delete(target,true);if(movedOld&&Directory.Exists(backup))Directory.Move(backup,target);}throw;
  } finally {if(Directory.Exists(stage)){try{Directory.Delete(stage,true);}catch{}}}
  PrunePrevious(target,oldPointer,warnings);
  if(shortcut){try{Type type=Type.GetTypeFromProgID("WScript.Shell");dynamic shell=Activator.CreateInstance(type);dynamic link=shell.CreateShortcut(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory),"오름목.lnk"));link.TargetPath=Path.Combine(target,"OreumMok.exe");link.WorkingDirectory=target;link.IconLocation=Path.Combine(target,"oreummok.ico")+",0";link.Save();}catch{warnings.Add("프로그램 설치는 완료됐지만 바탕화면 바로가기를 만들지 못했습니다.");}}
  if(launch){try{Process.Start(new ProcessStartInfo(Path.Combine(target,"OreumMok.exe")){WorkingDirectory=target});}catch{warnings.Add("설치는 완료됐습니다. 실행파일을 직접 열어주세요.");}}
  if(warnings.Count>0)File.WriteAllText(Path.Combine(target,"installation-warnings.txt"),String.Join(Environment.NewLine,warnings));return warnings.Count==0?"설치와 파일 검증을 완료했습니다.":String.Join(Environment.NewLine,warnings);
 }
 [STAThread]static int Main(string[] args){Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);try{if(args.Contains("--silent")){string flag=args.FirstOrDefault(x=>x.StartsWith("--target="));if(flag==null)throw new IOException("Silent installation requires --target.");Run(flag.Substring(9),!args.Contains("--no-shortcut"),!args.Contains("--no-launch"));return 0;}Application.Run(new SetupForm());return 0;}catch(Exception e){if(args.Contains("--silent")){string log=args.FirstOrDefault(x=>x.StartsWith("--log="));if(log!=null)File.WriteAllText(log.Substring(6),e.ToString());return 1;}MessageBox.Show(e.Message,"오름목 설치 오류");return 1;}}
}
