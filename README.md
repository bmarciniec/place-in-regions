# Place in regions

Allplan extension for placing rebars along line in regions with variable spacing.

## Installation

Copy the `Library` and `PythonPartsScripts` directories directly to `std` or `usr`
directory of Allplan. The PythonPart can be started from the Allplan's Library
from:

    Office (or Private) -> PythonParts -> Place in regions

## Usage

1.  Create a rebar shape in Allplan using native function _Bar shape_.
    Do not place it!
2.  Start the PythonPart.
3.  Select the created rebar shape
4.  Draw line to place the shape along it
5.  Define the placement regions in the property palette as a single string, like:

        5*50 + 10*100 + $*200 + 10*100 + 5*50

    With the string like this, the shape will be placed 5 times with a spacing of
    50 mm and subsequently 10 times with a spacing of 100 mm, beginning from both
    ends of the placement line. The remaining length will be filled with bars placed
    every 200 mm
