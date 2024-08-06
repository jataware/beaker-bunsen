FROM python:3.12
RUN useradd -m jupyter
EXPOSE 8888

RUN apt update && apt install -y lsof

# Install Python requirements
RUN pip install --upgrade --no-cache-dir hatch pip
# Bunsen requirements
RUN pip install --no-cache-dir "beaker-kernel~=1.6.1" "archytas~=1.1.6" "chromadb~=0.4.22" "numpy<2.0" "tenacity~=8.2.3" "tiktoken~=0.5.2" "marko~=2.0.3" "hatchling" "click~=8.1.7"
# pyrenew and dependencies
RUN pip install --no-cache-dir "multisignal-epi-inference@git+https://github.com/CDCgov/multisignal-epi-inference.git" "arviz"
COPY --link . /bunsen
RUN pip install -e /bunsen
RUN pip install pytest

# Switch to non-root user. It is crucial for security reasons to not run jupyter as root user!
USER jupyter
WORKDIR /jupyter

# Service
CMD ["beaker", "notebook", "--ip", "0.0.0.0"]
