from os import environ

# Set up memory database (no file)
environ['LATIGO_INTERNAL_DATABASE']="sqlite://"

from azure.eventhub import Offset

from latigo.event_hub.offset_persistence import DBOffsetPersistance, MemoryOffsetPersistance

class TestOffsetPersistence:

    def test_get_set(self):
        for op in [MemoryOffsetPersistance(), DBOffsetPersistance('tester')]:
            assert not op.get()
            offset=1337
            op.set(offset)
            ret=op.get()
            assert ret==offset
