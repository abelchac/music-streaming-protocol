Instructions for Suitable Environment:
	EC2:
		In terminal use "sudo apt-get install python2.7" to install
		python2 if it not already on the EC2 Server

Instruction for Running Code:

	Server: 
		python2.7 server.py 55353 [music directory]

	Client: 
		python client.py [ec2 instance ip] 55353


Using the Client:
	Commands:
		list :
			Will Return a list of all songs and IDs
		play <songID> :
			Will play a song with the given ID
		stop :
			Will stop the song that is currently playing 
		quit : 
			Will quit out of the client and close the connection
	Note:
		Information from response is written after the user prompt i.e. ">> [data]" after a LIST command. Press ENTER to refresh the prompt.