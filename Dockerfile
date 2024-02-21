# Alternative for the docker image: 
# https://github.com/joyzoursky/docker-python-chromedriver/blob/master/py-debian/3.9-selenium/Dockerfile
FROM selenium/standalone-chrome

# Run commands as root
USER root

# Copy the repository and install the python package and dependencies
COPY . /workspace
WORKDIR /workspace

# Install Python pip and then install the package
RUN wget https://bootstrap.pypa.io/get-pip.py && \
    python3 get-pip.py && \
    python3 -m pip install --no-cache-dir --upgrade pip && \
    pip install --use-pep517 --no-cache-dir -e . 

# Expose port 8080
EXPOSE 8080

# Make sure the startup script is executable
RUN chmod +x /workspace/startup.sh

# Define the command to run the application
CMD ["/bin/bash", "/workspace/startup.sh"]