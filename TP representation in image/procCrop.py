import cv2
import math
import numpy as np

''' first, create compositional overlay of ROI and cells'''

#overlays true positives over greater image...
background = cv2.imread("001.tif")
overlay = cv2.imread("001_cell.tif")
#... and writes to combined.tif
added_image = cv2.addWeighted(background,1, overlay, 2, 0)
cv2.imwrite("combined.tif",added_image)

'''
newBackground = cv2.imread("combined.tif")
ROI_overlay = cv2.imread("001_block.tif")

roi_cells_img = cv2.addWeighted(newBackground,1,ROI_overlay,2,0)
cv2.imwrite("combined.tif",roi_cells_img)
'''




#import bounding box
img = cv2.imread("001_block.tif")

# print(img.shape)

filename = "001_block.tif"
img = cv2.imread(filename)
gray = cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)

gray = np.float32(gray)
dst = cv2.cornerHarris(gray,2,3,0.04)

ret,dst = cv2.threshold(dst,0.1*dst.max(),255,0)
dst = np.uint8(dst)
ret,labels,stats,centroids = cv2.connectedComponentsWithStats(dst)
criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.001)
corners = cv2.cornerSubPix(gray,np.float32(centroids),(5,5),(-1,-1),criteria)

# inner corners are collected for array, denoting where ROIs exist in the image to be processed next 
cornerArr = []
for i in range(1, len(corners)):
    if(i != 3 and i != 4 and i != 5 and i != 6 and i != len(corners)):
        # gives (406, 406, 3) w/ round up in crop_image.shape
            # round down: 405,405,3
        cornerArr.append(corners[i])
                ## indexes 1 and 3, 2 and 4, 5 and 7, and 6 and 8 need to be averaged, though leads to 399x399
    print(corners[i]) #debugging info to monitor iteration

    
#result is dilated for marking corners; not important
dst = cv2.dilate(dst,None)

# Threshold for an optimal value; may vary depending on image
img[dst>0.01*dst.max()] = [0,0,255]


  # variables rounded down
x_min = int(round(cornerArr[0][0]))
x_max = int(round(cornerArr[1][0]))
y_min = int(round(cornerArr[0][1]))
y_max = int(round(cornerArr[2][1]))


'''
   # rounded up 
x_min = int(math.ceil(cornerArr[0][0]))
x_max = int(math.ceil(cornerArr[1][0]))
y_min = int(math.ceil(cornerArr[0][1]))
y_max = int(math.ceil(cornerArr[2][1]))
'''

print("y min:")
print(y_min)
print("y max:")
print(y_max)
print("x min:")
print(x_min)
print("x max:")
print(x_max)


crop_img = img[y_min:y_max, x_min:x_max]
print(crop_img.shape)

#import combined, full-sized image
basefilename = "combined.tif"
base_img = cv2.imread(basefilename)
base_crop = base_img[y_min:y_max,x_min:x_max]
print(base_img.shape)
cv2.imshow("basecrop",base_crop)
cv2.imwrite("ROI.tif",base_crop)
cv2.waitKey(0)












### miscellaneous notes below:

''' basic implementation of Harris corner detection before corners represented: 
#feature detection i.e. Harris Corner Detection
# neat source here
# https://opencv-python-tutroals.readthedocs.io/en/latest/py_tutorials/py_feature2d/py_features_harris/py_features_harris.html#harris-corners

import cv2
import numpy as np

filename = "image.png"
img = cv2.imread(filename)
gray = cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)

gray = np.float32(gray)
dst = cv2.cornerHarris(gray,2,3,0.04)

#result is dilated for marking corners; not important
dst = cv2.dilate(dst,None)

# Threshold for an optimal value; may vary depending on image
img[dst>0.01*dst.max()] = [0,0,255]

cv2.imshow("dst",img)
if cv2.waitKey(0) & 0xff == 27:
    cv2.destroyAllWindows()

'''



'''
for testing purposes, we just want these and this range systemitized
[530.5  76.5]
[923.5  76.5]
[530.5 469.5]
[923.5 469.5]

They are systemitized in the following way: only the 3rd, 4th, 5th, and 6th i-valued corners are valid since this
algorithm looks for both the inside and outside bounds of what is a roughly 7 pixel-thick yellow bounding box for the
ROI


A raw print-out reads as followS:

[523.5583    69.558266]
[929.4416    69.558266]
[530.5  76.5]
[923.5  76.5]
[530.5 469.5]
[923.5 469.5]
[523.5583 475.4416]
[929.4416  475.44156]
'''

'''
## variables rounded up 
# y range
y_min = math.ceil(cornerArr[0][1])
y_max = math.ceil(cornerArr[2][1])
# x range 
x_min = math.ceil(cornerArr[0][0])
x_max = math.ceil(cornerArr[1][0])


'''



'''
blue = img[100,100,0] #returns place where a color is 
    img.item(10,10,2) #access RED value
img.itemset((10,10,2),100) #sets value there
img.item(10,10,2) #returns 100 

'''

# print(img.size) #image size returned 
# print(img.dtype) #datatype returned


# neat reference here
# https://www.pyimagesearch.com/2014/01/20/basic-image-manipulations-in-python-and-opencv-resizing-scaling-rotating-and-cropping/


# neat reference for tgz unzip here
# https://superuser.com/questions/80019/how-can-i-unzip-a-tar-gz-in-one-step-using-7-zip





          
