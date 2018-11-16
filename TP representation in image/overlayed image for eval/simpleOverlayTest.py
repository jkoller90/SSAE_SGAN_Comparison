import cv2

background = cv2.imread("001.tif")
overlay = cv2.imread("001_cell.tif")

added_image = cv2.addWeighted(background,1, overlay, 2, 0)

cv2.imwrite("combined.tif",added_image)

newBackground = cv2.imread("combined.tif")
ROI_overlay = cv2.imread("001_block.tif")

roi_cells_img = cv2.addWeighted(newBackground,1,ROI_overlay,2,0)
cv2.imwrite("combined.tif",roi_cells_img)
