# EpiCam

A minimal acquisition software for taking pictures with a PointGray camera.


## Installation

- clone the repo locally
- create a python environment for the software
    ```
    conda create -n camera_env python==3.10
    conda activate camera_env
    conda install numpy maplotlib pillow
    ```
- from the camera manufacturer website:
    - download and install Spinnker SDK
    - download and install the Python connector (the download link is in the same page)


## Usage 
- Change `Exposure time` and `Gain` to adjust the image brightness
- If you need the exposure time to be longer you can lower the `framerate`
- Copy the current image with annotations to the clipboard with the button
`to clipboard`



