deploy: main.py bottle.py mcc-daq-server.service
	scp $^ pi@192.168.2.9:
	ssh pi@192.168.2.9 chmod +x ./main.py

dev: deploy
	ssh -t pi@192.168.2.9 ./main.py
