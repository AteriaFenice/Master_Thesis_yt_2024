from OpenGL.GL import*
import numpy as np
from PIL import Image
from math import ceil
import array
from itertools import repeat

import SpoutGL

import pyglet
import yt
import yt_idv

import asyncio
import openspace
#from openspace_api import*

from pathlib import Path

# Spout variables
SENDER_NAME_COLOR = "OpenSpace-yt-Color"
SENDER_NAME_DEPTH = "OpenSpace-yt-Depth"

TARGET_FPS = 30

DISPLAY_WIDTH = 800
DISPLAY_HEIGHT = 800
SEND_WIDTH = ceil(DISPLAY_WIDTH / 1)
SEND_HEIGHT = ceil(DISPLAY_HEIGHT / 1)


# Get the pixel data from the buffer
# buffer: Color-> GL_RGBA, Depth-> GL_DEPTH_COMPONENT
# n: nr of layer in the array
def getPixelData(buffer):
    # Read the pixel data from the depth buffer
    buffer = glReadPixels(0, 0, SEND_WIDTH, SEND_HEIGHT, buffer, GL_FLOAT)
    pixels_array = np.frombuffer(buffer, dtype=np.float32)

    np.seterr(divide='ignore', invalid='ignore')
    # Normalize the depth values to the range [0, 1]
    pixels_array = (pixels_array - pixels_array.min()) / (pixels_array.max() - pixels_array.min())
        
    return pixels_array

# Save the color texture from the buffer as an image
def saveImageColor(imageName):
    # Read the buffer to get the pixel data and reshape the array
    color_array = getPixelData(GL_RGBA).reshape((SEND_HEIGHT, SEND_WIDTH, 4))
    color_array = (color_array * 255).astype(np.uint8)

    # Save the color array as an image
    img = Image.fromarray(color_array, 'RGBA')
    img = img.transpose(method=Image.FLIP_TOP_BOTTOM)
    img.save(imageName)

# Save the depth buffer as an image
def saveImageDepth(imageName):
    # Read the depth buffer data and reshape to a 2D array
    depth_array = getPixelData(GL_DEPTH_COMPONENT).reshape((SEND_HEIGHT, SEND_WIDTH))
    depth_array = (depth_array * 255).astype(np.uint8)

    # Save the depth array as an image
    img = Image.fromarray(depth_array)
    img = img.transpose(method=Image.FLIP_TOP_BOTTOM)
    img.save(imageName)
    
def getFilePath():
    return Path(input())
    
    
# Main function
async def main():
    # Initialize senders
    sender_color = SpoutGL.SpoutSender()
    sender_color.setSenderName(SENDER_NAME_COLOR)

    sender_depth = SpoutGL.SpoutSender()
    sender_depth.setSenderName(SENDER_NAME_DEPTH)
    
    # Name of data files, can only do one set of files
    """ fname = "M6_100_Plot/turbsph_hdf5_plt_cnt_0001"
    pname = "M6_100_Particle/turbsph_hdf5_part_0001"
    """
    print("Enter simulation file path ")
    fname = getFilePath()
    print("Enter particle simulation file path ")
    pname = getFilePath()
    
    # Load files with yt
    ds = yt.load(fname, particle_filename=pname, unit_system="cgs")
    dd = ds.all_data()
    
    print("Enter a field: ")
    d1 = [item[1] for item in ds.field_list]
    print(d1)
    field_input = input()

    # Intitialize render context witg yt-idv and add scene 
    rc = yt_idv.render_context(height=SEND_HEIGHT, width=SEND_WIDTH, title="yt-OpenSpace", gui=False)
    sg = rc.add_scene(dd, field_input, no_ghost=True)
    print("\n")

    # Get the color and depth ID's from the render context
    color_id = rc.texture_id
    depth_id = rc.depth_texture_id
    
    # Initialize the depth texture
    # Create an empty array for all RGBA channels the same size as the depth texture
    depth_pixels = np.zeros((SEND_HEIGHT, SEND_WIDTH, 4), dtype=np.float32)
    # These will stay the same all the time so set them outside the loop
    # Blue and green channels will be 0 and the red channel gets updated in the while loop
    depth_pixels[:, :, 3] = 1 # alpha
    
    glBindTexture(GL_TEXTURE_2D, depth_id)
    
    # Set depth texture parameters
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    
    glBindTexture(GL_TEXTURE_2D, 0)
    
    # Initialize the color texture
    # Create an empty array for all RGBA channels the same size as the color texture
    color_pixels = np.zeros((SEND_HEIGHT, SEND_WIDTH, 4), dtype=np.float32)
    
    #Set color texture parameters
    glBindTexture(GL_TEXTURE_2D, color_id)
    glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
    glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
    
    glBindTexture(GL_TEXTURE_2D, 0)
    
    # OpenSpace API
    #earth_task = asyncio.create_task(subscribeToEarthScaleUpdates())
       
    while pyglet.app.windows:
        pyglet.clock.tick()
        
        for window in pyglet.app.windows:
            
            window.switch_to()
            window.dispatch_events()
            # Calls on the function on_draw
            # The one that renders the scene for the pyglet application
            window.dispatch_event("on_draw") 
            window.flip()
            
        camerapos = sg.camera.get_cameraposition()
        
        # Closes the window  
        if window.has_exit:
            break
            
        # --------------------------- Depth Texture --------------------------
        # Creating a depth texture by first reading the pixel data from the depth buffer
        # and then adding the pixel data to a color texture on the red channel only
        
        # Get the pixel data from the depth buffer and assign the pixel data only to the red channel
        depth_pixels[:, :, 0] = getPixelData(GL_DEPTH_COMPONENT).reshape(SEND_WIDTH, SEND_HEIGHT)
        #depth_pixels[:, :, 0] = np.flipud(depth_pixels[:, :, 0])

        glBindTexture(GL_TEXTURE_2D, depth_id)
        
        # Create a RGBA texture from the depth pixel data
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, SEND_WIDTH, SEND_HEIGHT, 0, GL_RGBA, GL_FLOAT, depth_pixels)
        
        # Send the texture
        sender_depth.sendTexture(depth_id, GL_TEXTURE_2D, SEND_WIDTH, SEND_HEIGHT, True, 0)
        
        # Indicate that the frame is ready to read
        sender_depth.setFrameSync(SENDER_NAME_DEPTH)
        
        # Save depth texture as an image
        #saveImageDepth("ytOpenSpace_depth.png")
                
        glBindTexture(GL_TEXTURE_2D, 0)
        
        # ------------------------- Color Texture --------------------------
        # Get the pixel data from the buffer
        # Reshape to a (width, height, 4) array to fit the RGBA array
        color_array = getPixelData(GL_RGBA).reshape(SEND_WIDTH, SEND_HEIGHT, 4)
        
        # Add the color pixel data to the RGBA array in their respective color channels
        color_pixels[:, :, :3] = color_array[:, :, :3]

        # Find all pixels that are the background color(black) and set their opacity (alpha) to 0
        # The rest have the opacity 1
        black_pixels = np.all(color_pixels[:, :, :3] <= 0.0, axis=-1)
        color_pixels[:, :, 3] = np.where(black_pixels, 0.0, 1.0)
                
        #Set color texture parameters
        glBindTexture(GL_TEXTURE_2D, color_id)
        
        # Create a color texture from the pixel data
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, SEND_WIDTH, SEND_HEIGHT, 0, GL_RGBA, GL_FLOAT, color_pixels)
        glBindTexture(GL_TEXTURE_2D, color_id)
        
        # Send color texture with spout
        sender_color.sendTexture(
            color_id, GL_TEXTURE_2D, SEND_WIDTH, SEND_HEIGHT, True, 0)
        
        # Indicate that the frame is ready to read
        sender_color.setFrameSync(SENDER_NAME_COLOR)
        
        # Save the texture as an image
        #saveImageColor("ytOpenSpace-color.png")
            
        glBindTexture(GL_TEXTURE_2D, 0)
        
        # Able to run the other functions at the same time despite the while true loop
        await asyncio.sleep(1 /TARGET_FPS)
        
           

if __name__ == "__main__":
    print('Program Start')
    asyncio.run(main())