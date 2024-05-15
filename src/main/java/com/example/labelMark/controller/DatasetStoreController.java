package com.example.labelMark.controller;

import com.example.labelMark.domain.DatasetStore;
import com.example.labelMark.domain.ImageInfo;
import com.example.labelMark.domain.Task;
import com.example.labelMark.domain.TaskDatasetInfo;
import com.example.labelMark.service.DatasetStoreService;
import com.example.labelMark.service.TaskService;
import com.example.labelMark.utils.ResultGenerator;
import com.example.labelMark.vo.constant.Result;
import org.springframework.web.bind.annotation.*;

import javax.annotation.Resource;
import javax.swing.event.ListDataEvent;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * <p>
 *  前端控制器
 * </p>
 *
 * @author hjw
 * @since 2024-05-08
 */
@RestController
@RequestMapping("/datasetStore")
public class DatasetStoreController {

    @Resource
    private DatasetStoreService datasetStoreService;

    @Resource
    private TaskService taskService;

    // isPublic设置默认值为0？
    @PostMapping("getDataset")
    public Result getDataset(int taskId, int isPublic){
        DatasetStore datasetStore = new DatasetStore();
        datasetStore.setTaskId(taskId);
        datasetStore.setIsPublic(isPublic);
        datasetStoreService.createDataset(datasetStore);
        int sampleId = datasetStore.getSampleId();
        return ResultGenerator.getSuccessResult(sampleId);
    }

    @GetMapping("/getTotalImgNumBySampleId")
    public Result getTotalImgNumBySampleId(int sampleId){
        int sum = datasetStoreService.getTotalImgNumBySampleId(sampleId);
        return ResultGenerator.getSuccessResult(sum);
    }


    @GetMapping("/findImgSrcTypeNameBySampleId")
    public Result findImgSrcTypeNameBySampleId(int sampleId, int pageSize, int current){
        List<ImageInfo> imageInfo = datasetStoreService.findImgSrcTypeNameBySampleId(sampleId, pageSize, current);
        return ResultGenerator.getSuccessResult(imageInfo);
    }


    @GetMapping("/getDataSet")
    public Result getDataSet(String username, int isAdmin, int isPublic) {

        List<Map<String, Object>> taskIdArr;

        if (isAdmin == 1) {
            System.out.println("Admin查询");
            taskIdArr = taskService.findAllTask();
        } else {
            System.out.println("User查询");
            if (isPublic == 1) {
                taskIdArr = taskService.findPublicTask();
            } else {
                taskIdArr = taskService.findTasksByUsername(username);
            }
        }
        System.out.println(taskIdArr);

        Map<String, Object> res = new HashMap<>();;
        if (!taskIdArr.isEmpty()) {

            List<Map<String, Object>> taskDatasetInfos = new ArrayList<>();
            List<String> usernameLists = new ArrayList<>();


            for (Map<String, Object> map : taskIdArr) {

                Object value = map.get("task_id");
                System.out.println(value);
                List<Map<String, Object>> datasetInfoList = datasetStoreService.findDatasetByTaskId((Integer) value);
                taskDatasetInfos.addAll(datasetInfoList);

                List<String> userList = taskService.findUserListByTaskId((Integer) value);
                usernameLists.addAll(userList);

            }

            if (!taskDatasetInfos.isEmpty()) {
                res.put("taskDatasetInfos", taskDatasetInfos);
                res.put("usernameLists", usernameLists);
            }

        }
        return ResultGenerator.getSuccessResult(res);
    }


    @GetMapping("/getSampleImageList")
    public Result getSampleImageList(int pageSize, int current, int sampleId){
        int total = datasetStoreService.getTotalImgNumBySampleId(sampleId);
        List<ImageInfo> imageInfos = datasetStoreService.findImgSrcTypeNameBySampleId(sampleId, pageSize, current);
        Map<String, Object> res = new HashMap<>();
        res.put("total", total);
        res.put("imageInfos", imageInfos);

        return ResultGenerator.getSuccessResult(res);
    }

    @PutMapping("/setDatasetStatus")
    public Result setDatasetStatus(int isPublic, int sampleId){
        datasetStoreService.updateDatasetStatusBySampleId(isPublic, sampleId);
        return ResultGenerator.getSuccessResult();
    }

//    @GetMapping("/generateDataset")
//    private Result generateDataset(int taskId){
//
//        Integer idExist = datasetStoreService.hasGenerateDataset(taskId);
//
//        if(idExist != null){
//            System.out.println("该样本已存在");
//            return ResultGenerator.getSuccessResult("该样本已存在");
//        }else {
//            Task task = taskService.selectTaskById(taskId);
//
//        }
//
//
//    }

}
