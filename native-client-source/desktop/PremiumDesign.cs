using System;using System.IO;using System.Linq;using System.Drawing;using System.Drawing.Drawing2D;using System.Drawing.Text;using System.Windows.Forms;
namespace OreumMok {
static class Premium {
[System.Runtime.InteropServices.DllImport("gdi32.dll",CharSet=System.Runtime.InteropServices.CharSet.Unicode)]static extern int AddFontResourceEx(string name,uint flags,IntPtr reserved);
static readonly PrivateFontCollection fonts=new PrivateFontCollection();
static Premium(){string dir=Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"assets","fonts");foreach(string name in new[]{"GothicA1-Regular.ttf","GothicA1-SemiBold.ttf"}){string file=Path.Combine(dir,name);if(File.Exists(file)){fonts.AddFontFile(file);AddFontResourceEx(file,0x10,IntPtr.Zero);}}}
public static FontFamily Family {get{return fonts.Families.FirstOrDefault(f=>f.Name=="Gothic A1")??fonts.Families.FirstOrDefault()??new FontFamily("Malgun Gothic");}}
public static GraphicsPath Rounded(Rectangle rect,int radius){var p=new GraphicsPath();int d=Math.Min(radius*2,Math.Min(rect.Width,rect.Height));p.AddArc(rect.X,rect.Y,d,d,180,90);p.AddArc(rect.Right-d,rect.Y,d,d,270,90);p.AddArc(rect.Right-d,rect.Bottom-d,d,d,0,90);p.AddArc(rect.X,rect.Bottom-d,d,d,90,90);p.CloseFigure();return p;}
}
sealed class BrandBanner:Panel {
public BrandBanner(){DoubleBuffered=true;Height=155;Width=950;Margin=new Padding(0,0,0,22);Resize+=(s,e)=>Invalidate();}
protected override void OnPaint(PaintEventArgs e){base.OnPaint(e);var g=e.Graphics;g.SmoothingMode=SmoothingMode.AntiAlias;Rectangle bounds=new Rectangle(0,0,Width-1,Height-1);using(var clip=Premium.Rounded(bounds,18)){g.SetClip(clip);using(var fill=new LinearGradientBrush(bounds,Style.Green,Color.FromArgb(37,67,55),20))g.FillRectangle(fill,bounds);using(var pen=new Pen(Color.FromArgb(16,255,255,255),1))for(int i=0;i<10;i++)g.DrawBezier(pen,Width-340,15+i*15,Width-210,120+i*5,Width-80,-30+i*12,Width+10,100+i*11);}
g.ResetClip();using(var gold=new SolidBrush(Color.FromArgb(220,191,137)))using(var white=new SolidBrush(Color.FromArgb(247,244,236)))using(var muted=new SolidBrush(Color.FromArgb(192,205,194)))using(var title=new Font(Premium.Family,Width<700?19:25,FontStyle.Bold))using(var body=new Font(Premium.Family,10)){g.DrawString("OREUM MOK  /  WOOD & LIGHT",body,gold,25,20);g.DrawString("나무의 결에, 빛을 더하다.",title,white,22,48);g.DrawString("원목 계단과 조명 시공을 위한 오름목 업무 공간",body,muted,25,112);}
if(Width>700){float x=Width-190,y=125;for(int i=0;i<4;i++){float px=x+i*24,py=y-i*23;PointF[] top={new PointF(px,py-10),new PointF(px+68,py-10),new PointF(px+88,py-21),new PointF(px+20,py-21)};using(var wood=new SolidBrush(Color.FromArgb(177+i*9,124+i*8,72+i*8)))g.FillPolygon(wood,top);using(var side=new SolidBrush(Color.FromArgb(114,79,49)))g.FillRectangle(side,px,py-10,68,7);using(var glow=new Pen(Color.FromArgb(236,209,147),2))g.DrawLine(glow,px+2,py-9,px+65,py-9);}}}
}
}
