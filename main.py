from src import bot
import subprocess
import os

if __name__ == '__main__':
    if "DOCKER_HOST" in os.environ:
        print("Environment is Docker")
        print("Installing requirementsDocker.txt")
        subprocess.run(["pip", "install", "-r", "requirementsDocker.txt"])
    else:
        print("Environment is not Docker")
        print("Installing requirements.txt")
        subprocess.run(["pip", "install", "-r", "requirements.txt"])
    
    bot.run_discord_bot()