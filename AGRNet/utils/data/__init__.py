def get_dataset(dataset_name):
    if dataset_name == 'cornell':
        from .cornell_data import CornellDataset
        return CornellDataset
    elif dataset_name == 'cbrgd':
        from .cbrgd_data import CBRGDDataset
        return CBRGDDataset
    else:
        raise NotImplementedError('Dataset Type {} is Not implemented'.format(dataset_name))
