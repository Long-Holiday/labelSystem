package com.example.labelMark.service.impl;

import com.example.labelMark.domain.DatasetStore;
import com.example.labelMark.domain.ImageInfo;
import com.example.labelMark.domain.SampleImg;
import com.example.labelMark.domain.TaskDatasetInfo;
import com.example.labelMark.mapper.DatasetStoreMapper;
import com.example.labelMark.mapper.SampleImgMapper;
import com.example.labelMark.service.DatasetStoreService;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;

import javax.annotation.Resource;
import java.util.List;
import java.util.Map;

/**
 * <p>
 *  服务实现类
 * </p>
 *
 * @author hjw
 * @since 2024-05-08
 */
@Service
public class DatasetStoreServiceImpl extends ServiceImpl<DatasetStoreMapper, DatasetStore> implements DatasetStoreService {

    @Resource
    private DatasetStoreMapper datasetStoreMapper;

    @Resource
    private SampleImgMapper sampleImgMapper;

    @Override
    public Integer createDataset(int taskId) {
        DatasetStore datasetStore = new DatasetStore();
        datasetStore.setTaskId(taskId);
        datasetStore.setIsPublic(0);
        datasetStoreMapper.createDataset(datasetStore);
        int sampleId = datasetStore.getSampleId();
        return sampleId;
    }

    @Override
    public List<Map<String, Object>> findDatasetByTaskId(int taskId) {
        List<Map<String, Object>> taskDatasetInfos = datasetStoreMapper.findDatasetByTaskId(taskId);
        return taskDatasetInfos;
    }

    @Override
    public void updateDatasetStatusBySampleId(int isPublic, int sampleId) {
        datasetStoreMapper.updateDatasetStatusBySampleId(isPublic, sampleId);
    }

    @Override
    public void insertSampleImgInfo(int sampleId, int typeId, String imgSrc) {
        SampleImg sampleImg = new SampleImg();
        sampleImg.setSampleId(sampleId);
        sampleImg.setTypeId(typeId);
        sampleImg.setImgSrc(imgSrc);
        sampleImgMapper.insert(sampleImg);
    }

    @Override
    public void deleteDatastoreById(int sampleId) {
        datasetStoreMapper.deleteById(sampleId);
    }

    @Override
    public int getTotalImgNumBySampleId(int sampleId) {
        int num = datasetStoreMapper.getTotalImgNumBySampleId(sampleId);
        return num;
    }

    @Override
    public List<ImageInfo> findImgSrcTypeNameBySampleId(int sampleId, int pageSize, int current) {
        List<ImageInfo> imageInfo = datasetStoreMapper.findImgSrcTypeNameBySampleId(sampleId, pageSize, current);
        return imageInfo;
    }

    @Override
    public Integer hasGenerateDataset(int taskId) {
        Integer res = datasetStoreMapper.hasGenerateDataset(taskId);
        return res;
    }
}
