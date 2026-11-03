# -*- coding: utf-8 -*-
"""
Created on Fri Feb 13 18:26:31 2026

@author: cidve
"""
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

# ================= CONFIG =================

datasets=[
 #"Flat",r"Z:\Projects\Kepler\Halbach\70mT_800ppm_62mm\Flat\BFOV_histogram_flat_discrete_70mT_800ppms.txt"),
 ("Cubes",r"Z:\Projects\Kepler\Halbach\50mT_237ppm_zigzag_HalfCubeAlternated\Magnets_histogram_nonlinear_discrete_50mT_237ppms_zigzag.txt"),
 ("Cylinders",r"Z:\Projects\Kepler\Halbach\50mT_891ppms_cylindricalCubes\Magnets_histogram_nonlinear_50mT_zigzag_cylindricalCubes.txt"),
]

ref="Cubes"
Magnet_info="Kepler-zigzag,50mT, Nonlinear,CubeVsCylinder)"
FOV_info="Sphere(340mm)"# Ellipsoid:75x78x78 mm"

color_horizontal="grey"
color_vertical="indianred"

# ================= GEOMETRÍA =================

r_m=0.340/2
V_sphere=4/3*np.pi*r_m**3
print(f"Sphere volume = {V_sphere:.6e} m³")

# ================= REBIN CONSERVATIVO =================

def rebin_cont(x,h,edges):
    bw=np.mean(np.diff(x)); e=np.concatenate([[x[0]-bw/2],x+bw/2]); hn=np.zeros(len(edges)-1); i=0
    for j in range(len(hn)):
        a,b=edges[j],edges[j+1]
        while i<len(h) and e[i+1]<=a: i+=1
        k=i
        while k<len(h) and e[k]<b:
            ov=min(b,e[k+1])-max(a,e[k])
            if ov>0: hn[j]+=h[k]*(ov/(e[k+1]-e[k]))
            k+=1
    return 0.5*(edges[:-1]+edges[1:]),hn

# ================= LECTURA =================

raw={}; bw={}
for lab,p in datasets:
    d=np.loadtxt(p,comments='%'); raw[lab]=(d[:,0],d[:,1]); bw[lab]=np.mean(np.diff(d[:,0]))
    print(f"{lab} raw volume = {np.sum(d[:,1]):.6e}")

target_bw=max(bw.values())
xmin=min(x.min() for x,_ in raw.values()); xmax=max(x.max() for x,_ in raw.values())
edges=np.arange(xmin-target_bw/2,xmax+target_bw,target_bw)

data={lab:rebin_cont(*raw[lab],edges) for lab in raw}

print("\n=== REBIN VOLUME CHECK ===")
for lab,(x,h) in data.items():
    print(f"{lab:10s} → {np.sum(h):.6e}  ratio={np.sum(h)/V_sphere:.3f}")

# ================= REFERENCIA =================

x_ref,h_ref=data[ref]
iref=np.argmax(h_ref)
xpk_ref,hpk_ref=x_ref[iref],h_ref[iref]

# ================= PLOT FINAL =================

fig,ax=plt.subplots(figsize=(8,5))

for lab,(x,h) in data.items():

    m=h>0; i=np.argmax(h); xp,hp=x[i],h[i]
    ls='-.' if lab==ref else ':'; lw=1.5 if lab==ref else 1.2
    ax.plot(x[m],h[m],label=lab,zorder=3)
    ax.axhline(hp,linestyle=ls,linewidth=lw,color=color_horizontal,zorder=2)
    ax.axvline(xp,linestyle=ls,linewidth=lw,color=color_vertical,zorder=2)

    if lab==ref:
        th=f"{lab} (ref) Hmax = {hp:.3e}"
        tv=f"Bmax = {xp:.3f} mT (ref)"
    else:
        dH=(hp-hpk_ref)/hpk_ref*100
        dB=(xp-xpk_ref)/xpk_ref*100
        th=f"{lab} Hmax = {hp:.3e} ({dH:+.1f}%)"
        tv=f"Bmax = {xp:.3f} mT ({dB:+.2f}%)"

    ax.annotate(th, (xp, hp),
                xytext=(6, 2), textcoords="offset points",
                fontsize=10, color=color_horizontal)
    
    ax.annotate(tv, (xp, hp),
                xytext=(6, -10), textcoords="offset points",
                fontsize=10, color=color_vertical)
    
ax.set_xlabel("By (mT)")
ax.set_ylabel("Magnetic volume per bin [m³]")

ax.set_title(
    f"$\\it{{Magnet:\\ {Magnet_info},\\ FOV:\\ {FOV_info}}}$\n"
    f"BFOV Histogram (rebinned to ΔB = {target_bw*1000:.4g} µT)",
    pad=30
)

ax.legend(loc="upper left")

fig.text(0.99,0.01,datetime.now().strftime("%Y-%m-%d"),
         ha='right',va='bottom',fontsize=10,color='gray',alpha=0.8)

plt.tight_layout()
plt.show()



#%%# ================= DESMAGNETIZACIÓN — HISTOGRAMA REBIN FÍSICO =================

import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

# ------------------ CONFIG ------------------

datasets=[
 #"Flat",r"Z:\Projects\Kepler\Halbach\70mT_800ppm_62mm\Flat\BFOV_histogram_flat_discrete_70mT_800ppms.txt"),
 ("Linear",r"Z:\Projects\Kepler\Halbach\70mT_800ppm_62mm\Nonlinear\Shimming_linear\Main_magnets_histogram_Kepler_nonlinear_70mT_800ppm_with_shimming_linear.txt"),
 ("Nonlinear",r"Z:\Projects\Kepler\Halbach\70mT_800ppm_62mm\Nonlinear\Shimming_nonlinear\Main_magnets_histogram_Kepler_nonlinear_70mT_800ppm_with_shimming_nonlinear.txt"),
]

ref = "Linear"

curve_colors = {"Linear":"dodgerblue","Nonlinear":"darkorange"}
color_horizontal = "grey"
color_vertical   = "crimson"

Magnet_info = "Kepler"
FOV_info    = "Diameter:340 mm"

# ------------------ REBIN CONSERVATIVO ------------------

def rebin_histogram_continuous(X,H,new_edges):
    bw=np.mean(np.diff(X)); edges=np.concatenate([[X[0]-bw/2],X+bw/2]); Hn=np.zeros(len(new_edges)-1); i=0
    for j in range(len(Hn)):
        a,b=new_edges[j],new_edges[j+1]
        while i<len(H) and edges[i+1]<=a: i+=1
        k=i
        while k<len(H) and edges[k]<b:
            ov=min(b,edges[k+1])-max(a,edges[k])
            if ov>0: Hn[j]+=H[k]*(ov/(edges[k+1]-edges[k]))
            k+=1
    return 0.5*(new_edges[:-1]+new_edges[1:]), Hn

# ------------------ LECTURA ------------------

raw_data={}; bw_dict={}
for label,path in datasets:
    d=np.loadtxt(path,comments='%'); raw_data[label]=(d[:,0],d[:,1]); bw_dict[label]=np.mean(np.diff(d[:,0]))

target_bw=max(bw_dict.values())

xmin=min(x.min() for x,_ in raw_data.values())
xmax=max(x.max() for x,_ in raw_data.values())
edges=np.arange(xmin-target_bw/2,xmax+target_bw,target_bw)

data_dict={label:rebin_histogram_continuous(*raw_data[label],edges) for label in raw_data}

# ------------------ REFERENCIA ------------------

M_ref,H_ref=data_dict[ref]; iref=np.argmax(H_ref)
M_peak_ref,H_peak_ref=M_ref[iref],H_ref[iref]

# ------------------ PLOT ÚNICO ------------------

fig,ax=plt.subplots(figsize=(8,5))

for label,(M,H) in data_dict.items():
    mask=H>0; i=np.argmax(H); Mp,Hp=M[i],H[i]
    ls='-.' if label==ref else ':'; lw=1.9 if label==ref else 1.2

    ax.plot(M[mask],H[mask],label=label,color=curve_colors.get(label,"black"),zorder=2)
    ax.axhline(Hp,linestyle=ls,linewidth=lw,color=color_horizontal,zorder=4)
    ax.axvline(Mp,linestyle=ls,linewidth=lw,color=color_vertical,zorder=4)

    if label==ref:
        th=f"{label} (ref) Hmax = {Hp:.3e}"; tv=f"Mmax = {Mp:.4f} T"
    else:
        th=f"{label} Hmax = {Hp:.3e} ({(Hp-H_peak_ref)/H_peak_ref*100:+.1f}%)"
        tv=f"Mmax = {Mp:.4f} T ({(Mp-M_peak_ref)/M_peak_ref*100:+.2f}%)"


    ax.text(Mp,Hp,th,fontsize=10,color=color_horizontal)
    ax.text(Mp,Hp*0.93,tv,fontsize=10,color=color_vertical)

ax.set_xlabel("Magnetization M (T)")
ax.set_ylabel("Magnetic volume per bin [m³]")
ax.set_title(f"$\\it{{Magnet:\\ {Magnet_info},\\ FOV:\\ {FOV_info}}}$\nDemagnetization Histogram (rebinned to ΔM = {target_bw*1000:.4g} mT)",pad=30)
ax.legend(loc="upper left")

fig.text(0.99,0.01,datetime.now().strftime("%Y-%m-%d"),ha='right',va='bottom',fontsize=10,color='gray',alpha=0.8)

plt.tight_layout(); plt.show()
