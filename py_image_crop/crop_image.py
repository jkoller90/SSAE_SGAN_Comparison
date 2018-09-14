"""
http://pillow.readthedocs.io/en/5.1.x/reference/Image.html#PIL.Image.Image.load
http://pillow.readthedocs.io/en/5.1.x/reference/Image.html
http://effbot.org/imagingbook/image.htm#tag-Image.Image.crop
"""

from PIL import Image


img = Image.open("test_image.png")
# area = (400, 400, 800, 800)
    # left, top, right, bottom
# w, h = img.size

"""
w = 34
h = 34

area = (0,0, w, h)
cropped_img = img.crop(area)
# img.show()
cropped_img.show()

second_area = (6,6,w+6,w+6)
second_cropped_img = img.crop(second_area)
second_cropped_img.show()
#yourImage.crop((0, 30, w, h-30)).save(...)
""" 

#loop over til the end:
	#for til the end of a row 
def ResetText():
	row_text = "row"
	col_text = "col"
	save_text=""

l = 0
t = 0
r_w = 34
b_h = 34
row = 1
col = 1 
row_text = "./image_crops/row"
col_text = "col"
png_text = ".png"
row_idx = 1
col_idx = 1 
save_text = ""
# "row1_col1.png"
#range(y-size/34)
for row in range(15): #64-5
	#range(x-size/34)
	for col in range(80): #64-5
		# print(l)
		cropped_img = img.crop((l,t,r_w,b_h))
		# cropped_img.show()
		# cropped_img.save("row%dcol%d.png",row,col)
		row_text+=str(row_idx)
		col_text+=str(col_idx)
		save_text+= row_text + col_text + png_text
		cropped_img.save(save_text)
		row_text = "./image_crops/row"
		col_text = "col"
		save_text=""
		l+=6
		r_w+=6
		row+=1
		col+=1
		col_idx+=1
	# l=0
	t+=6
	b_h+=6

"""
# left, top, right, bottom
	row+=1
	row_text += str(row)
	l = 0
	r_w = 34
	t+=6
	b_h+=6
"""