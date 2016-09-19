function [] = myelin( path )

%addpath(genpath('/Users/viherm/axon_segmentation/code'))

cd (path)

path_Mask = 'AxonMask';
path_img = 'image.jpg';

load (path_Mask)

im_in = imread(path_img);
size(im_in) 

AxSeg = prediction;
PixelSize = 0.3;

%Myelin Segmentation

[AxSeg_rb,~]=RemoveBorder(AxSeg,PixelSize);
backBW=AxSeg & ~AxSeg_rb; % backBW = axons that have been removed by RemoveBorder
[im_out] = myelinInitialSegmention(im_in, AxSeg_rb, backBW,0,1,PixelSize);

im_out = myelinCleanConflict(im_out, im_in,0.5); % 

axonlist = as_myelinseg2axonlist(im_out,PixelSize)

save axonlist.mat axonlist

imwrite(sum(im_out,3),'myelin.jpg')

end

