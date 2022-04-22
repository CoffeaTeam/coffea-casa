FROM jupyterhub/k8s-hub:0.11.1

USER root

# Install pyjwt dependency needed for generation of the tokens 
RUN pip3 install pyjwt pymacaroons

# Check if you want to update design of coffea-casa hub image
COPY coffea_casa_trans.png /usr/local/share/jupyterhub/static/images/coffea_casa_trans.png

USER ${NB_USER}

CMD ["jupyterhub", "--config", "/usr/local/etc/jupyterhub/jupyterhub_config.py"]
