#!/usr/local/bin/python3 -u

# Useful blog: https://stackoverflow.com/questions/56736043/extract-building-edges-from-map-image-using-python
# import the necessary packages
import argparse
import imutils
import cv2
import sys
import numpy as np 
import json
import urllib.request
from urllib.error import HTTPError

def findCanvasId(mainfest, image_id):
    if isinstance(manifest['sequences'], list):
        sequences = manifest['sequences']
    else:
        sequences = [ manifest['sequences'] ]
    for sequence in sequences:
        if isinstance(sequence['canvases'], list):
            canvases = sequence['canvases']
        else:
            canvases = [ sequence['canvases'] ]
        for canvas in canvases:
            if searchForType(canvas, '@id', image_id) or searchForType(canvas, '@id', image_id[:-1]):
                return canvas['@id']
            else:
                print ('Not found {} or {} in {}'.format(image_id, image_id[:-1], canvas['@id']))
    return None            
    
def searchForType(node, key, value):
    if isinstance(node, dict):
        if key in node and node[key] == value:
            print ('FOUND {} = {}'.format(key, value))
            return node
        else:
            for mapKey in node:
                if isinstance(node[mapKey], list) or isinstance(node[mapKey], dict):
                    response = searchForType(node[mapKey], key, value)
                    if response:
                        return response
                        
    if isinstance(node, list):
        for element in node:
            response = searchForType(element, key, value)
            if response:
                return response
    return None                

def getJson(url):
    count = 0
    while count < 3:
        try:
            response = urllib.request.urlopen(url)
            return json.loads(response.read().decode())
        except HTTPError as error:
            count += 1

    raise error

# construct the argument parse and parse the arguments
ap = argparse.ArgumentParser()
ap.add_argument("-i", "--image", required=True, help="IIIF image ID")
ap.add_argument("-m", "--manifest", required=True, help="Manifest which contains this image")
ap.add_argument("-d", "--demo", required=False, help="Show image segmentation, useful for demos. Press space to cycle through", action="store_true")
ap.add_argument("-o", "--output", required=False, help="Filename for generated annotationlist", default="annotations.json")
ap.add_argument("-e", "--example", required=False, help="Example image showing areas found", default="demo.jpg")
ap.add_argument("-min", "--min", required=False, help="Minimum threshold for area of shape between 0 and 1", default=0.001)
ap.add_argument("-max", "--max", required=False, help="Maximum threshold for area of shape between 0 and 1", default=0.4)
ap.add_argument("-s", "--size", required=False, help="Size of IIIF image to download. Use IIIF size syntax e.g. 2000,", default='2000,')
args = vars(ap.parse_args())

iiif_id = args["image"] 
demo=False
if "demo" in args and args['demo']:
    demo=True
    print ('demo: -{}-'.format(args['demo']))
if iiif_id[-1] != '/':
    iiif_id += '/'

print ('Getting URL {}'.format(args["manifest"]))
manifest = getJson(args["manifest"])

print ('Getting URL {}info.json'.format(iiif_id))
infoJson = getJson("{}info.json".format(iiif_id))

canvas_id = findCanvasId(manifest, iiif_id)    
if not canvas_id:
    print ('Failed to find {} in {}'.format(iiif_id, args["manifest"]))
    sys.exit(-1)

if 'llgc.org.uk' in iiif_id and args["size"] == '2000,':
    url = '{}full/pct:40/0/default.jpg'.format(iiif_id)
else:
    url = '{}full/{}/0/default.jpg'.format(iiif_id, args["size"])

TMP_IMG_NAME = 'download.jpg'
print ('Getting {}'.format(url))
count = 0
completed=False
while count < 3:
    try: 
        urllib.request.urlretrieve(url, TMP_IMG_NAME)
        completed=True
        break
    except HTTPError as error:
        count += 1
 
if not completed:
    raise error

# load the image, convert it to grayscale, blur it slightly,
# and threshold it
image = cv2.imread(TMP_IMG_NAME)
height, width, channels = image.shape
size_ratio = infoJson['width'] / width 

print ('Ratio {}'.format(size_ratio))
gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
blurred = cv2.GaussianBlur(gray, (5, 5), 0)
#for i in range(-10,20):
#    #thresh = cv2.threshold(blurred, i, 255, cv2.THRESH_BINARY)[1]
#    print ('trying {}'.format(i))
#    thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY,11,i)
#    cv2.imwrite('{}_ad_threshed.jpg'.format(i), thresh)
#sys.exit(-1)

thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY,11,2)
#thresh = cv2.threshold(blurred, 180, 255, cv2.THRESH_BINARY)[1]
canny = thresh
#canny = cv2.Canny(thresh, 50, 0, 6)
#kernel = np.ones((3,3), dtype=np.uint8)
#closed = cv2.morphologyEx(thresh, cv2.MORPH_DILATE,kernel)


#cv2.imwrite('both_threshed.jpg', thresh)

#cv2.imshow("Thresh", thresh)
#cv2.waitKey(0)
if demo:
    cv2.imshow("Image", canny)
    cv2.waitKey(0)

# find contours in the thresholded image
cnts = cv2.findContours(canny.copy(), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
cnts = imutils.grab_contours(cnts)

print ('Total contors found {}'.format(len(cnts)))
max_area = width * height
largerCnts = []
for c in cnts:
    bounding = cv2.boundingRect(c)
    contorArea = bounding[2] * bounding[3]
    if contorArea / max_area > args["min"] and contorArea / max_area < args["max"]:
        largerCnts.append(c)
        
cnts = largerCnts        
print ('Contors within size bounds found {}'.format(len(cnts)))
annos = []
# loop over the contours
count = 1
for c in cnts:
	# compute the center of the contour
    M = cv2.moments(c)
    if M["m00"] != 0:
        #demoImage = thresh
        demoImage = image
        cX = int(M["m10"] / M["m00"])
        cY = int(M["m01"] / M["m00"])
        bounding = cv2.boundingRect(c)
        contorArea = bounding[2] * bounding[3]
        #print ('Area {} Proportion: {}, area {} maxArea: {}'.format(contorArea, ((contorArea / max_area) * 100), contorArea, max_area))
        #print ('Bounding {} bounding area {}'.format(bounding, bounding[2] * bounding[3]))
        #print (c[0][0][0])
        #print (type(c[0]))
        #print (type(c[0][0]))
        #print (type(c[0][0][0]))
        #print (len(c[0]))
     
        # draw the contour and center of the shape on the image
        cv2.drawContours(demoImage, [c], -1, (0, 255, 0), 2)
        cv2.circle(demoImage, (cX, cY), 7, (255, 255, 255), -1)
        cv2.putText(demoImage, "center", (cX - 20, cY - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
     
        # show the image
        if demo:
            cv2.imshow("Image", demoImage)
            cv2.waitKey(0)
        points = []
        path = 'M'
        for pointList in c:
            for point in pointList:
               # print (point)
                points.append((point[0].item() * size_ratio, point[1].item() * size_ratio))
                path += '{},{} '.format(point[0].item() * size_ratio, point[1].item() * size_ratio)

        path = path[:-1] + 'Z'
        #dwg = svgwrite.Drawing('test.svg', profile='tiny', size=(width * size_ratio, height * size_ratio))
        #polygon = svgwrite.shapes.Polyline(points=points)
        #dwg.add(polygon)
        #dwg.save()
        
        annos.append({
            "@context": "http://iiif.io/api/presentation/2/context.json",
            "@type": "oa:Annotation",
            "motivation" : [ "oa:commenting" ],
            "resource": [
                {
                    "@type" : "dctypes:Text",
                    "format" : "text/html",
                    "chars" : "<p>Shape {}</p>".format(count)
                }
            ],
            "on" :  {
                "@type" : "oa:SpecificResource",
                "within" : {
                  "@id" : "{}".format(manifest['@id']),
                  "@type" : "sc:Manifest"
                },
                "selector" : {
                  "@type" : "oa:Choice",
                  "default" : {
                    "@type" : "oa:FragmentSelector",
                    "value" : "xywh={},{},{},{}".format(bounding[0], bounding[1], bounding[2], bounding[3])
                  },
                  "item" : {
                    "@type" : "oa:SvgSelector",
                    "value" : "<svg xmlns='http://www.w3.org/2000/svg'><path xmlns=\"http://www.w3.org/2000/svg\" d=\"{}\"  id=\"rough_path_c8a67c00-247c-453a-bf83-e37d88be598b\" fill-opacity=\"0\" fill=\"#00bfff\" fill-rule=\"nonzero\" stroke=\"#00bfff\" stroke-width=\"1\" stroke-linecap=\"butt\" stroke-linejoin=\"miter\" stroke-miterlimit=\"10\" stroke-dasharray=\"\" stroke-dashoffset=\"0\" font-family=\"none\" font-weight=\"none\" font-size=\"none\" text-anchor=\"none\" style=\"mix-blend-mode: normal\"/></svg>".format(path)
                  }
                },
                "full" : "{}".format(canvas_id)
              } 
            
        })
        count += 1

       # break;

    # <svg xmlns='http://www.w3.org/2000/svg'><path xmlns=\"http://www.w3.org/2000/svg\" d=\"M5286.33477,2466.51724l166.73851,84.88506l6.06322,118.23276l-100.0431,33.3477l-130.3592,-87.91667l57.60057,-151.58046z\" data-paper-data=\"{&quot;strokeWidth&quot;:1,&quot;editable&quot;:true,&quot;deleteIcon&quot;:null,&quot;annotation&quot;:null}\" id=\"rough_path_c8a67c00-247c-453a-bf83-e37d88be598b\" fill-opacity=\"0\" fill=\"#00bfff\" fill-rule=\"nonzero\" stroke=\"#00bfff\" stroke-width=\"1\" stroke-linecap=\"butt\" stroke-linejoin=\"miter\" stroke-miterlimit=\"10\" stroke-dasharray=\"\" stroke-dashoffset=\"0\" font-family=\"none\" font-weight=\"none\" font-size=\"none\" text-anchor=\"none\" style=\"mix-blend-mode: normal\"/></svg>

print ('Saving demo image to {}'.format(args["example"]))
cv2.imwrite(args["example"], demoImage)     

annoList = {
    "@context": "http://iiif.io/api/presentation/2/context.json",
    "@id": "http://localhost:8888/examples/anno_list.json",
    "@type": "sc:AnnotationList",
    "resources": annos
}

output_filename = args["output"]
with open(output_filename, 'w') as outfile:
    json.dump(annoList, outfile, indent=4)
print ('Saved annotation list to {}'.format(output_filename))    
