// SPDX-License-Identifier: MIT
// Ycrystal branding (POV-Ray 3.7+)
// A reproducible 3D logo: a Y-shaped atomic chain and wordmark.
// A wireframe cage is available as an opt-in experiment, but is OFF by default.
// No faces, triangles, mesh, polygons or translucent surfaces.
//
// Choose an output by passing `Declare=LogoMode=N` on the command line:
//   0: horizontal Y + "crystal" wordmark (default, 8:3)
//   1: isolated atomic Y mark (square, transparent-ready)
//   2: rounded-square dark app/Dock icon (square, transparent-ready)
//
// Examples (run in this directory):
//   povray +Iycrystal_logo.pov +Ologo.png +W1920 +H720 +FN +A0.1 +R3 -D
//   povray +Iycrystal_logo.pov +Otransparent.png +W1920 +H720 +FN +UA +A0.1 +R3 -D Declare=TransparentBackground=1
//   povray +Iycrystal_logo.pov +Omark.png +W1024 +H1024 +FN +UA +A0.1 +R3 -D Declare=LogoMode=1
//   povray +Iycrystal_logo.pov +Oicon.png +W1024 +H1024 +FN +UA +A0.1 +R3 -D Declare=LogoMode=2
//
// All default settings are defined only if absent, so a call-site can
// override the numbers with `Declare=Option=Value`.

#version 3.7;

#ifndef(LogoMode)       #declare LogoMode = 0;       #end
#ifndef(ShowWireframe)  #declare ShowWireframe = 0;  #end
#ifndef(AtomRadius)     #declare AtomRadius = 0.285; #end
#ifndef(BondRadius)     #declare BondRadius = 0.095; #end
#ifndef(FontMode)       #declare FontMode = 0;       #end
#ifndef(TransparentBackground) #declare TransparentBackground = 0; #end
#ifndef(UseWhiteBg)     #declare UseWhiteBg = 1;     #end
#ifndef(WordGap)        #declare WordGap = 0.20;     #end

// FontMode=0 uses built-in Cyrvetic (font 2) from POV-Ray 3.7.
// For a locally installed .ttf, set FontMode=1 and edit the path below.
#declare ExternalFont = "Lato-Bold.ttf";

global_settings { assumed_gamma 1.0 max_trace_level 6 }

// True transparency: no floor, sky, backdrop mesh, or shadow-catching plane.
// +UA enables PNG alpha. TransparentBackground=1 selects a fully transparent
// background and overrides the usual white background setting.
#if (TransparentBackground)
  background { color rgbt <1,1,1,1> }
#else
  #if (UseWhiteBg)
    background { color rgb <1,1,1> }
  #else
    background { color rgb <0.08,0.12,0.20> }
  #end
#end

#if (LogoMode = 0)
  // Tight 8:3 horizontal format, designed for 1920x720 or 1600x600.
  // Molecular Y + wordmark occupy nearly the entire image height.
  camera {
    orthographic
    location <0.15,0,-25>
    look_at <0.15,0,0>
    right x*10.0
    up y*3.75
  }
#else
  camera {
    orthographic
    location <0,0,-25>
    look_at <0,0,0>
    right x*4.62
    up y*4.62
  }
#end

// Deterministic lighting: no jitter, no external HDRI or image maps.
light_source {
  <-6,8,-11> color rgb <1.00,0.99,0.98>*1.08
  area_light <2.0,0,0>, <0,2.0,0>, 4,4 adaptive 1
}
light_source { <6,3,-7> color rgb <0.72,0.83,1.00>*0.66 }
light_source { <0,-5,-8> color rgb <1,1,1>*0.25 }

#declare Cobalt = texture {
  pigment { color rgb <0.075,0.32,0.83> }
  finish { ambient 0.075 diffuse 0.52 specular 0.92 roughness 0.016 reflection 0.06 }
};
#declare CenterBlue = texture {
  pigment { color rgb <0.035,0.23,0.71> }
  finish { ambient 0.08 diffuse 0.52 specular 0.96 roughness 0.015 reflection 0.07 }
};
#declare Steel = texture {
  pigment { color rgb <0.72,0.78,0.87> }
  finish { ambient 0.095 diffuse 0.58 specular 0.78 roughness 0.022 reflection 0.05 }
};
#declare CageSteel = texture {
  pigment { color rgb <0.72,0.80,0.90> }
  finish { ambient 0.10 diffuse 0.68 specular 0.54 roughness 0.032 }
};
#declare PaleVertex = texture {
  pigment { color rgb <0.83,0.89,0.98> }
  finish { ambient 0.11 diffuse 0.66 specular 0.72 roughness 0.028 }
};
#declare WordBlue = texture {
  pigment { color rgb <0.045,0.13,0.33> }
  finish { ambient 0.15 diffuse 0.68 specular 0.30 roughness 0.045 }
};
#declare IconNavy = texture {
  pigment { color rgb <0.025,0.10,0.23> }
  finish { ambient 0.20 diffuse 0.78 specular 0.12 roughness 0.09 }
};

#macro Atom(P, R, T)
  sphere { P, R texture { T } }
#end

#macro Bond(A, B, R, T)
  cylinder { A, B, R texture { T } }
#end

// This motif is purposely kept simple to work down to 32 x 32 pixels.
// Coordinates are LOCAL, in the xy plane.
#declare Hub = <0,0,-0.50>;
#declare LeftTip = <-1.22,1.30,-0.50>;
#declare RightTip = <1.22,1.30,-0.50>;
#declare StemTip = <0,-1.40,-0.50>;

#macro MolecularY()
  union {
    Bond(Hub,LeftTip,BondRadius,Steel)
    Bond(Hub,RightTip,BondRadius,Steel)
    Bond(Hub,StemTip,BondRadius,Steel)
    Atom(Hub,AtomRadius*1.16,CenterBlue)
    Atom(LeftTip,AtomRadius,Cobalt)
    Atom(RightTip,AtomRadius,Cobalt)
    Atom(StemTip,AtomRadius,Cobalt)
  }
#end

// OPTIONAL experimental wire-only motif behind the Y. Default is OFF.
// No polyhedron faces. A rear depth prevents its links from hiding the Y arms.
#macro CrystalWire()
  #local T = <0,2.00,0.47>;
  #local L = <-1.57,0.15,0.47>;
  #local R = <1.57,0.15,0.47>;
  #local B = <0,-1.16,0.47>;
  #local WireR = 0.021;
  union {
    Bond(T,L,WireR,CageSteel)
    Bond(T,R,WireR,CageSteel)
    Bond(L,B,WireR,CageSteel)
    Bond(R,B,WireR,CageSteel)
    Bond(L,R,WireR*0.76,CageSteel)
    Bond(T,B,WireR*0.76,CageSteel)
    Atom(T,0.087,PaleVertex)
    Atom(L,0.087,PaleVertex)
    Atom(R,0.087,PaleVertex)
    Atom(B,0.087,PaleVertex)
  }
#end

// Build a physically rounded square from boxes and 4 cylinders.
// Its rear face is away from the camera (positive z).
#macro IconTile()
  union {
    box { <-1.60,-2.02,0.90>, <1.60,2.02,1.16> }
    box { <-2.02,-1.60,0.90>, <2.02,1.60,1.16> }
    cylinder { <-1.60,-1.60,0.90>, <-1.60,-1.60,1.16>, 0.42 }
    cylinder { <-1.60, 1.60,0.90>, <-1.60, 1.60,1.16>, 0.42 }
    cylinder { < 1.60,-1.60,0.90>, < 1.60,-1.60,1.16>, 0.42 }
    cylinder { < 1.60, 1.60,0.90>, < 1.60, 1.60,1.16>, 0.42 }
    texture { IconNavy }
  }
#end

// The capital Y is the FIRST LETTER of ycrystal; the text therefore
// spells ONLY "crystal". Do not add another "y" to the text.
#if (LogoMode = 0)
  #declare MarkShift = <-2.65,0.04,0>;
  #if (ShowWireframe)
    object { CrystalWire() translate MarkShift }
  #end
  object { MolecularY() translate MarkShift }

  #if (FontMode = 0)
    #declare NameObject = text { internal 2 "crystal" 0.06, 0 };
  #else
    #declare NameObject = text { ttf ExternalFont "crystal" 0.06, 0 };
  #end

  #declare TextMin = min_extent(NameObject);
  #declare TextMax = max_extent(NameObject);
  #declare WidthScale  = 5.75/(TextMax.x-TextMin.x);
  #declare HeightScale = 1.31/(TextMax.y-TextMin.y);

  object {
    NameObject
    scale <WidthScale,HeightScale,1>
    translate <(-1.15+WordGap)-TextMin.x*WidthScale,
               -1.01-TextMin.y*HeightScale,-0.08>
    texture { WordBlue }
  }

#else
  #if (LogoMode = 2)
    IconTile()
  #end
  // The full cage can be useful for a larger emblem; leave it off in
  // default app icons for legibility at 16 px / 32 px / 64 px.
  #if (ShowWireframe)
    #if (LogoMode = 1)
      CrystalWire()
    #end
  #end
  MolecularY()
#end
