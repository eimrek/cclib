"""
cclib (http://cclib.sf.net) is (c) 2006, the cclib development team
and licensed under the LGPL (http://www.gnu.org/copyleft/lgpl.html).
"""

__revision__ = "$Revision: 668 $"


import re

# If numpy is not installed, try to import Numeric instead.
try:
    import numpy
except ImportError:
    import Numeric as numpy

import utils
import logfileparser

class ORCA(logfileparser.Logfile):
    """An ORCA log file."""

    def __init__(self, *args):

        # Call the __init__ method of the superclass
        super(ORCA, self).__init__(logname="ORCA", *args)
        
    def __str__(self):
        """Return a string representation of the object."""
        return "ORCA log file %s" % (self.filename)

    def __repr__(self):
        """Return a representation of the object."""
        return 'ORCA("%s")' % (self.filename)
    
    def normalisesym(self, label):
        """Use standard symmetry labels instead of Gaussian labels.

        To normalise:
        (1) If label is one of [SG, PI, PHI, DLTA], replace by [sigma, pi, phi, delta]
        (2) replace any G or U by their lowercase equivalent

        >>> sym = Gaussian("dummyfile").normalisesym
        >>> labels = ['A1', 'AG', 'A1G', "SG", "PI", "PHI", "DLTA", 'DLTU', 'SGG']
        >>> map(sym, labels)
        ['A1', 'Ag', 'A1g', 'sigma', 'pi', 'phi', 'delta', 'delta.u', 'sigma.g']
        """

    def before_parsing(self):

        # Used to index self.scftargets[].
        SCFRMS, SCFMAX, SCFENERGY = range(3)
        # Flag that indicates whether it has reached the end of a geoopt.
        self.optfinished = False
        # Flag for identifying Coupled Cluster runs.
        self.coupledcluster = False

    def extract(self, inputfile, line):
        """Extract information from the file object inputfile."""

        if line[0:15] == "Number of atoms":

            natom = int(line.split()[-1])
            if hasattr(self, "natom"):
                # I wonder whether this code will ever be executed.
                assert self.natom == natom
            else:
                self.natom = natom

        if line[1:13] == "Total Charge":
#get charge and multiplicity info
            self.charge = int(line.split()[-1])
            line = inputfile.next()
            self.mult = int(line.split()[-1])

        if line[25:50] == "Geometry Optimization Run":
#get geotarget info
            line = inputfile.next()
            while line[0:23] != "Convergence Tolerances:":
                line = inputfile.next()

            self.geotargets = numpy.zeros((5,), "d")
            for i in range(5):
                line = inputfile.next()
                self.geotargets[i] = float(line.split()[-2])

        if line[33:53] == "Geometry convergence":
#get geometry convergence criteria
            if not hasattr(self, "geovalues"):
                self.geovalues = [ ]
            
            newlist = []
            headers = inputfile.next()
            dashes = inputfile.next()
            
            #check if energy change is present (steps > 1)
            line = inputfile.next()
            if line.find("Energy change") > 0:
                newlist.append(float(line.split()[2]))
                line = inputfile.next()
            else:
                newlist.append(0.0)

            #get rest of info
            for i in range(4):
                newlist.append(float(line.split()[2]))
                line = inputfile.next()
            
            self.geovalues.append(newlist)

        if line[0:21] == "CARTESIAN COORDINATES" and not hasattr(self, "atomcoords"):
#if not an optimization, determine structure used
            dashes = inputfile.next()
            
            atomnos = []
            atomcoords = []
            line = inputfile.next()
            while len(line) > 1:
                broken = line.split()
                atomnos.append(self.table.number[broken[0]])
                atomcoords.append(map(float, broken[1:4]))
                line = inputfile.next()

            self.atomcoords = [atomcoords]
            if not hasattr(self, "atomnos"):
                self.atomnos = atomnos
                self.natom = len(atomnos)
                
        if line[26:53] == "GEOMETRY OPTIMIZATION CYCLE":
#parse geometry coords
            stars = inputfile.next()
            dashes = inputfile.next()
            text = inputfile.next()
            dashes = inputfile.next()
           
            if not hasattr(self,"atomcoords"):
                self.atomcoords = []

            atomnos = []
            atomcoords = []
            for i in range(self.natom):
                line = inputfile.next()
                broken = line.split()
                atomnos.append(self.table.number[broken[0]])
                atomcoords.append(map(float, broken[1:4]))
            
            self.atomcoords.append(atomcoords)
            if not hasattr(self, "atomnos"):
                self.atomnos = numpy.array(atomnos,'i')

        if line[21:68] == "FINAL ENERGY EVALUATION AT THE STATIONARY POINT":
            text = inputfile.next()
            broken = text.split()
            assert int(broken[2]) == len(self.atomcoords)
            stars = inputfile.next()
            dashes = inputfile.next()
            text = inputfile.next()
            dashes = inputfile.next()

            atomcoords = []
            for i in range(self.natom):
                line = inputfile.next()
                broken = line.split()
                atomcoords.append(map(float, broken[1:4]))

            self.atomcoords.append(atomcoords)

        if line[0:16] == "ORBITAL ENERGIES":
#parser orbial energy information
            dashes = inputfile.next()
            text = inputfile.next()
            text = inputfile.next()

            self.moenergies = [[]]
            self.homos = [[0]]

            line = inputfile.next()
            while len(line) > 20: #restricted calcs are terminated by ------
                info = line.split()
                self.moenergies[0].append(float(info[3]))
                if float(info[1]) > 0.00: #might be 1 or 2, depending on restricted-ness
                    self.homos[0] = int(info[0])
                line = inputfile.next()

            line = inputfile.next()

            #handle beta orbitals
            if line[17:35] == "SPIN DOWN ORBITALS":
                text = inputfile.next()

                self.moenergies.append([])
                self.homos.append(0)

                line = inputfile.next()
                while len(line) > 20: #actually terminated by ------
                    info = line.split()
                    self.moenergies[1].append(float(info[3]))
                    if float(info[1]) == 1.00:
                        self.homos[1] = int(info[0])
                    line = inputfile.next()

        if line[1:32] == "# of contracted basis functions":
            self.nbasis = int(line.split()[-1])

        if line[0:14] == "OVERLAP MATRIX":
#parser the overlap matrix
            dashes = inputfile.next()

            self.aooverlaps = numpy.zeros( (self.nbasis, self.nbasis), "d")
            for i in range(0, self.nbasis, 6):
                header = inputfile.next()
                size = len(header.split())

                for j in range(self.nbasis):
                    line = inputfile.next()
                    broken = line.split()
                    self.aooverlaps[j, i:i+size] = map(float, broken[1:size+1])

        if line[0:18] == "MOLECULAR ORBITALS":
#parser the molecular orbital coefficients
            dashses = inputfile.next()

            mocoeffs = [ numpy.zeros((self.nbasis, self.nbasis), "d") ]
            self.aonames = []

            for spin in range(len(self.moenergies)):

                if spin == 1:
                    blank = inputfile.next()
                    mocoeffs.append(numpy.zeros((self.nbasis, self.nbasis), "d"))

                for i in range(0, self.nbasis, 6):
                    numbers = inputfile.next()
                    energies = inputfile.next()
                    occs = inputfile.next()
                    dashes = inputfile.next()
                    broken = dashes.split()
                    size = len(broken)

                    for j in range(self.nbasis):
                        line = inputfile.next()
                        broken = line.split()

                        #only need this on the first time through
                        if spin == 0 and i == 0:
                            atomname = line[3:5].split()[0]
                            num = int(line[0:3]) + 1
                            orbital = broken[1].upper()
                            
                            self.aonames.append("%s%i_%s"%(atomname, num, orbital))

                        temp = []
                        vals = line[16:-1] #-1 to remove the last blank space
                        for k in range(0, len(vals), 10):
                            temp.append(float(vals[k:k+10]))
                        mocoeffs[spin][i:i+size, j] = temp

            self.mocoeffs = mocoeffs

        if line[0:23] == "VIBRATIONAL FREQUENCIES":
#parse the vibrational frequencies
            dashes = inputfile.next()
            blank = inputfile.next()

            self.vibfreqs = numpy.zeros((3 * self.natom,),"d")

            for i in range(3 * self.natom):
                line = inputfile.next()
                self.vibfreqs[i] = float(line.split()[1])

        if line[0:11] == "IR SPECTRUM":
#parse ir intensities
            dashes = inputfile.next()
            blank = inputfile.next()
            header = inputfile.next()
            dashes = inputfile.next()

            self.vibirs = numpy.zeros((3 * self.natom,),"d")

            line = inputfile.next()
            while len(line) > 2:
                num = int(line[0:4])
                self.vibirs[num] = float(line.split()[2])
                line = inputfile.next()

        if line[0:14] == "RAMAN SPECTRUM":
#parser raman intensities
            dashes = inputfile.next()
            blank = inputfile.next()
            header = inputfile.next()
            dashes = inputfile.next()

            self.vibramans = numpy.zeros((3 * self.natom,),"d")

            line = inputfile.next()
            while len(line) > 2:
                num = int(line[0:4])
                self.vibramans[num] = float(line.split()[2])
                line = inputfile.next()



if __name__ == "__main__":
    import doctest, orcaparser
    doctest.testmod(orcaparser, verbose=False)