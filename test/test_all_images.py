


import glob, os, time, fabio.openimage, gzip, bz2, cProfile, pstats, sys

times = {}
images = []

for fname in glob.glob(os.path.join("testimages","*")):
    if fname.find("header_only")==-1:
        images.append(fname)

images.sort()

def shellbench(cmd, im):
    """
    The shell appears to be lying about it's performance. It claims 
    zero time to gunzip a file when it actually takes 200 ms. This is 
    cheating via a cache I suspect. We shall try to avoid this problem
    """ 
    if sys.platform != "win32":
        os.system("touch "+im)
        start = time.time()
        the_file = os.popen(cmd + " " +im,"rb").read()
        return time.time()-start

print "I/O 1  : Time to read the image"
print "I/O 2  : Time to read the image (repeat"
print "Fabio  : Time for fabio to read the image"
print "Shell  : Time for shell to do decompression"
print "Python : Time for python to do decompression\n"

print "I/O 1  I/O 2  Fabio  Shell  Python   Size/MB"
for im in images:
    # Network/disk io time first
    start = time.clock()
    the_file = open(im,"rb").read()
    times[im] =  [ time.clock()-start ]
    start = time.clock()
    # Network/disk should be cached
    the_file = open(im,"rb").read()
    times[im].append( time.clock() - start )
    start = time.clock()
    try:
        fim = fabio.openimage.openimage(im)
    except KeyboardInterrupt:
        raise
    except:
        print "Problem with",im
        continue
        # raise
    times[im].append( time.clock() - start )
    nt = 3 ; ns = 2
    # Now check for a fabio slowdown effect    
    if im[-3:] == '.gz':
        times[im].append(shellbench("gzip -cd ",im))
        nt += 1; ns -= 1
        start = time.clock()
        the_file = gzip.GzipFile(im,"rb").read()
        times[im].append( time.clock()-start )  
        nt += 1; ns -= 1
    if im[-4:] == '.bz2':
        times[im].append(shellbench("bzip2 -cd ",im))
        nt += 1 ; ns -= 1
        start = time.clock()
        the_file = bz2.BZ2File(im,"rb").read()
        times[im].append( time.clock()-start )  
        nt += 1; ns -= 1
    # Speed ratings in megabytes per second (for fabio)
    MB = len(the_file) / 1024.0 / 1024.0

    print ("%.4f "*nt + " "*7*ns)%tuple(times[im]),"%8.3f"%(MB), im

    cProfile.run("fabio.openimage.openimage(im)","stats")
    p = pstats.Stats("stats",stream = open("profile.txt","a"))
    p.strip_dirs().sort_stats(-1).print_stats()
    