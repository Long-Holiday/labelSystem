package com.example.labelMark.service;

import com.example.labelMark.domain.DatasetStore;
import com.baomidou.mybatisplus.extension.service.IService;
import com.example.labelMark.domain.ImageInfo;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

/**
 * <p>
 *  服务类
 * </p>
 *
 * @author hjw
 * @since 2024-05-08
 */
@Service
public interface DatasetStoreService extends IService<DatasetStore> {

    Integer createDataset(int taskId);

    List<Map<String, Object>> findDatasetByTaskId(int taskId);

    void updateDatasetStatusBySampleId(int isPublic, int sampleId);

    void insertSampleImgInfo(int sampleId, int typeId, String imgSrc);

    void deleteDatastoreById(int sampleId);

    int getTotalImgNumBySampleId(Integer sampleId);

    List<ImageInfo> findImgSrcTypeNameBySampleId(Integer sampleId, int pageSize, int current);

    Integer hasGenerateDataset(int taskId);
}
