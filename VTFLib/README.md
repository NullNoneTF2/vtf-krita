VTFLib
======

This is a Linux port of [VTFLib](http://nemesis.thewavelength.net/index.php?c=149).

> [!NOTE]
> I never studied the source of the original VTFLib, never pulled changes from
> upstream, and never really maintained this library.
>
> I only ported this library to Linux so I could look at the textures of Portal 2
> out of curiosity.

> [!WARNING]
> This library is written in a pretty unsafe way and might have buffer overflows
> related to its file parsing logic (or other places). In fact there is a read
> buffer overlow in `CVTFFile::Convert()` (as I was told by someone using ASAN),
> but I don't understand the code well enough to figure out what is going on.
>
> Only use this library with files that you *really* trust!
>
> It is also not endian safe. Meaning it only supports little-endian platforms
> and using it on a big-endian platform will not work at all and lead to crashes.

I was notified about several problems:

* Integer overflows in size calculations that then lead to write buffer overflows
  to undersized buffers.
* Wrong buffer size assumptions leading to (only a few byte) reads after the
  actual end of buffers.
* Calls of `delete[]` (and thus `free()`) of basically arbitrary memory in
  certain error conditions.

I tried to fix these issues, but make no guarantees of correctness and hope I
didn't break any valid files.

### Setup

	git clone https://github.com/panzi/VTFLib.git
	mkdir VTFLib/build
	cd VTFLib/build
	cmake .. -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr
	make -j`nproc`
	sudo make install

You may use the cmake option `-DUSE_LIBTXC_DXTN=ON`/`OFF` to enable/disable
support for writing S3TC compressed textures.

### Missing Features

There are several features that aren't currently supported by the Linux
version because they depend on a legacy Windows library
([nvDXTLib](http://developer.nvidia.com/object/dds_utilities_legacy.html)).
Such features are:

 * genratig mipmaps
 * resizing textures and generating thumbnails
 * generating normal maps/normal map conversion

However, all read-only features are supported.

### Dependencies

 * [libtxc\_dxtn](https://people.freedesktop.org/~cbrill/libtxc_dxtn/) for writing S3TC
   compressed textures (optional).
   
<details><summary>Installation</summary><p>
	
*From https://askubuntu.com/questions/1033209/libtxc-dxtn-libtxc-dxtni386-not-found-in-ppa-18-04-bionic#1047591*
```
# required stuff
sudo apt-get install mesa-common-dev
# get source files
cd ~/
wget https://people.freedesktop.org/~cbrill/libtxc_dxtn/libtxc_dxtn-1.0.1.tar.gz
tar xvfz libtxc_dxtn-1.0.1.tar.gz
cd libtxc_dxtn-1.0.1
# start the job
./configure
make
sudo make install
# clean up sources (optional)
cd ..
rm -rf libtxc_dxtn-1.0.1 libtxc_dxtn-1.0.1.tar.gz
```

</p></details>

### Documentation

[Doxygen API Reference](http://panzi.github.io/VTFLib/)

### Projects Using VTFLib for Linux

 * [pixbufloader-vtf](https://github.com/panzi/pixbufloader-vtf) - load VTF files in
   Gtk+ applications
 * [qvtf](https://github.com/panzi/qvtf) - load VTF files in Qt applications
 * [KIO Thumbnail VTF Plugin](https://github.com/panzi/KIO-VTF-Thumb-Creator) - show
   thumbnails for VTF files in KDE

### License

This library is free software; you can redistribute it and/or
modify it under the terms of the GNU Lesser General Public
License as published by the Free Software Foundation; either
version 2.1 of the License, or (at your option) any later version.

This library is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
Lesser General Public License for more details.
