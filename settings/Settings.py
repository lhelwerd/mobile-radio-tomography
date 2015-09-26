import json

class Settings(object):
    settings_files = {}

    @classmethod
    def get_settings(cls, file_name):
        """
        Retrieve the settings from a file name, load the JSON data and 
        unserialize it. We store the settings object statically in this class 
        so that later uses of the same settings file can reuse it.
        """

        if file_name not in cls.settings_files:
            with open(file_name) as data:
                cls.settings_files[file_name] = json.load(data)

        return cls.settings_files[file_name]

    def __init__(self, file_name, component_name):
        self.component_name = component_name
        
        settings = self.__class__.get_settings(file_name)
        
        self.settings = None
        if self.component_name in settings:
            self.settings = settings[self.component_name]["settings"]

    def get(self, key):
        if self.settings == None or key not in self.settings:
            raise KeyError("Setting '{}' for component '{}' not found.".format(key, self.component_name))

        return self.settings[key]
