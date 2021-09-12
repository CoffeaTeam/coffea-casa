Troubleshooting Common Issues
=========
In general, it is advised that you restart your coffea-casa server before doing further troubleshooting, so that you can ensure your instance is up-to-date. You can do this by going into the File menu, accessing the Hub Control Panel, and pressing the big red "Stop My Server" button.

.. image:: _static/coffea-casa-server_stop.png
   :alt: A demonstration of the "Stop My Server" button.
   :width: 50%
   :align: center

After the server is shut down, you will get a series of linear prompts to start it back up again. If the problem persists, then it's time for a deeper investigation!

Accessibility Issues
-----
**The coffea-casa server won't load, I get an error when trying to access the page, or I'm told there are certificate issues.**

There's a plethora of issues which seem specific to certain web browsers. If you run into any of these, please attempt to open coffea-casa in a different browser. Should this still fail, open a new issue.

If opening coffea-casa in a new browser solves the issue, you are still encouraged to provide information within `this issue <https://github.com/CoffeaTeam/coffea-casa/issues/93/>`_ to help us gather data.

**Running a manually-configured Dask cluster gives me a dashboard link, but the dashboard link does not work.**

This is expected behavior. If you go into the Dask sidebar of JupyterLab, however, the orange keys should still work and give you access to the information you'd find within the dashboard. If the keys are grey or any other problems arise, please submit an issue.

Runtime Issues
-----
**The terminal appears to terminate without an error, or I have noticed strange "core.####" files within my file browser.**

If your terminal is terminating without errors, please check for the aforementioned core files within your file browser. If they are present, then you are generating core dumps. In either case, report an issue on GitHub specifying what you are trying to do, which step is going wrong, and whether you are getting core dumps. This will help us pinpoint what's going wrong.

**I have installed a package through the terminal, but I still get ModuleNotFound errors when attempting to run my processor.**

Ensure that you have installed your package onto the workers as well. A guide for this can be found `here in our documentation <https://coffea-casa.readthedocs.io/en/latest/cc_packages.html>`_.