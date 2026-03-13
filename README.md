# **IMPORTANT!**



For this program to work, you must install **python** and following dependencies:



numpy

pygltflib

Pillow

pywebview



To install all of them at once:



install python first, then

py -3 -m pip install numpy pygltflib pillow pywebview

# 

# **Version 2.0**



### **Usage**



**Open command prompt in the folder where your converter and your glb are. Then, in the command prompt, input:**



**python glb2mod.py -g yourglb.glb -o out.mod --verbose --max-tex-size 128**



**yourglb.glb is to be replaced with your .glb model file**

**out.mod: the name can be anything, just make sure to keep the .mod at the end of it**

**--verbose is optional, but it tells you information regarding your textures**

**--max-tex-size can be anything between 4 to 128, anything more or less will either crash your game or make the texture super compressed**



### **Current Limitations**



* **You must join all of the objects in the mesh for it to work. Textures will be connected into one big material.**
* **If converting a skinned mesh, you must use the same bones as the armature of the model you are replacing in the game! Take not that even ship parts have an armature, so be careful and rig your models accordingly.**
* **I recommend using Meltytool to view your exported .MOD files.**
* **The game seems to only accept image textures downscaled 1-128 times. Thankfully, there is a downscaler in the converter.**
* **You must note use a model with too many vertices.**
* **Materials currently only import with textures. If your mesh has no textures, or a base color instead, in the game it will appear as gray.**



## **Future Goals:**



* **Work on a Local GUI**
* **Clean up code**



