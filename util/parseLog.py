import os
import numpy as np
import pandas as pd
import re
from datetime import datetime
import math

def getIndexOfWords( df, words ):
    return int(np.where( df['msg1'].str.contains(words))[0])

def getDataSets(a_dir):
    return [name for name in os.listdir(a_dir)
            if os.path.isdir(os.path.join(a_dir, name))]

def parseLog(setName):
	DIR = 'R:/data/'
	setDir = os.path.join( DIR, setName )
	logPath = os.path.join( setDir, 'log/tracker.log' )
	outPath = os.path.join( setDir, 'data/tracker.csv' )
	
	if (os.path.exists(outPath)):
		print "%s Ignored" % setName
		return

	data = []
	## Read through file, split on tab and add to data array 
	with open(logPath) as file:
		for line in file.readlines():
			out = line.rstrip().strip().split('\t')
			for elm in out:
				elm = elm.strip() #strip EOL chars
			data.append( out )         


	df = pd.DataFrame( data, columns = ['timestamp', 'msgType', 'emitter', 'blank', 'msg1', 'msg2', 'msg3'])
	## PARSING

	# Start of the video 
	vidStartRow = getIndexOfWords(df, 'Start Writing Video')
	# End of the video
	vidEndRow = getIndexOfWords(df, 'Stop Writing Video')

	# Resolution
	resLine = getIndexOfWords(df, '1 um')
	resString = df['msg2'][resLine]
	pixPerUm = float( resString.split(' ')[1] )
	resolution = pixPerUm * 1000 #now in pixels/mm

	# Subset Frames Where Written and Move
	writtenFrames = df[ df['msg1'].str.contains('wrote frame')]
	moveFrames = df[ df['msg1'].str.contains('From')]

	comb = pd.concat( [writtenFrames[['timestamp','msg1']], moveFrames[['timestamp','msg1']]] )

	comb = comb.sort_index()

	# Find first written frame
	firstFrameIx = comb.axes[0][0]

	if firstFrameIx < vidStartRow:
		comb[vidStartRow + 1 : vidEndRow - 1]


	f = '%Y-%m-%d %H:%M:%S,%f'

	# Calculate Elapsed Time in Seconds
	comb['timeElapsed'] = comb['timestamp']
	startTime = datetime.strptime( comb['timeElapsed'][firstFrameIx], f )
	comb['timeElapsed'] = comb['timeElapsed'].map( lambda x : (datetime.strptime( x, f ) ) )
	comb['timeElapsed'] = ( comb['timeElapsed'] - startTime ) / np.timedelta64(1, 's') #elapsed time

	comb = comb.sort(columns = 'timeElapsed')

	## Add columns to data frame
	comb['xmove'] = float(0)
	comb['ymove'] = float(0)
	comb['timeDelta'] = float(0) 

	## Compile regex
	pEx = re.compile('\(([^)]+)\)')
	intEx = re.compile('(-?\d+)')

	## Set to zero all variables we're about to use
	unitV = (0, 0)
	moving = 0
	timeElapsed = 0
	movedDist= 0
	totalDist = 0
	cumStepX = 0
	cumStepY = 0
	totalStepX = 0
	totalStepY = 0
	MOVEDUR = 0.210 ## Duration of a move
	NSKIP = 1 ## Number of frames immediately after a move to not apply move to
	te = 0

	c = 0
	### Interpolate move across frames for MOVEDUR
	for row in comb.iterrows():
		msg = row[1][1]
		ix = row[0]
		print c
		c = c + 1
		if 'wrote frame' in msg:
			deltaTime = comb['timeElapsed'][ix] - te
			te = comb['timeElapsed'][ix]
			comb['timeDelta'][ix] = deltaTime
			
			if moving:
				if skipframe:
					skipframe -= 1
					
				elif timeElapsed <= MOVEDUR:
					timeElapsed += deltaTime
					# Calculate distance moved from last frame
					movedDist = float(totalDist) * float(deltaTime) / float(MOVEDUR)
					comb['xmove'][ix] = float(movedDist) * unitV[0]
					comb['ymove'][ix] = float(movedDist) * unitV[1]
					
					cumStepX += comb['xmove'][ix]
					cumStepY += comb['ymove'][ix]
					
					## Force total of move to add up to totalSteps (on last frame)
					if abs(cumStepX) > abs(totalStepX) :
						comb['xmove'][ix] = totalStepX - (cumStepX - comb['xmove'][ix])
					if abs(cumStepY) > abs(totalStepY):
						comb['ymove'][ix] = totalStepY - (cumStepY - comb['ymove'][ix])

					
		else: #move instruction - parse text to get steps
			## Figure out from string what the X and Y instructions are in steps
			steps = pEx.findall(msg)[2]
			
			stepSep = intEx.findall(steps)
			totalStepX = float( stepSep[0] )
			totalStepY = float( stepSep[1] ) 
			
			totalDist = math.sqrt( totalStepX * totalStepX + totalStepY * totalStepY)

			# Calculate unit vector of motion based on totalSteps
			unitV = (float(totalStepX) / float(totalDist), float(totalStepY) / float(totalDist) )
			
			# Clear previous move's variables
			cumStepX = 0
			cumStepY = 0 
			moving = 1
			skipframe = NSKIP # to skip frames after move
			timeElapsed = 0 


	## Clean up
	final = comb[ comb['msg1'].str.contains('wrote frame')]
	final = final[['timeElapsed','timeDelta','xmove','ymove']]
	final = final.reset_index()
	final['PixPerMM'] = resolution
	final['MMPerSteps'] = 0.2
	final.index.names = ['frameNumber']
	final = final.drop('index', 1)
	final.to_csv(outPath)

	print "%s Parsed" % setName

for set in getDataSets("R:/data/"):
	parseLog(set)