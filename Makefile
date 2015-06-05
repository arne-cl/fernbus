
DATE=$(shell date -d "+1 week" -I)

test:
	fernbus stuttgart schwerin $(DATE)
	fernbus hamburg hannover $(DATE)
	fernbus barcelona sarajevo $(DATE)
	fernbus buxtehude aalen $(DATE)
