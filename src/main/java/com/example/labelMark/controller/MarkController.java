package com.example.labelMark.controller;

import com.example.labelMark.service.MarkService;
import com.example.labelMark.utils.ResultGenerator;
import com.example.labelMark.vo.constant.Result;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import javax.annotation.Resource;
import java.util.List;
import java.util.Map;

/**
 * <p>
 *  前端控制器
 * </p>
 *
 * @author hjw
 * @since 2024-04-28
 */
@RestController
@RequestMapping("/mark")
public class MarkController {

    @Resource
    private MarkService markService;

    @GetMapping("/saveMarkInfo")
    public Result saveMarkInfo(int taskId,  String jsonData) throws JsonProcessingException {

        ObjectMapper objectMapper = new ObjectMapper();
        List<Map<String, Object>> dataList = objectMapper.readValue(jsonData, List.class);

        for (Map<String, Object> data : dataList) {
            String typeId = (String) data.get("typeId");
//            System.out.println("typeId: " + typeId);
            // 过滤，检测typeArr中的typeId与geometryArr中的typeId信息是否相匹配
            // 将typeId匹配成功的geomtryArr添加到geomArr中
            List<String> geomArr = null;
        }

//        if(geomArr.size() == 0 ){
//            System.out.println("无标注信息");
//            for (Map<String, Object> data : dataList) {
//                String typeId = (String) data.get("typeId");
//                markService.deleteMarkByTypeId(taskId, Integer.parseInt(typeId));
//            }
//        }

        Boolean exist = markService.isMark(taskId);
        if(exist){
            System.out.println("存在task为："+taskId+"的mark");
            int i=0;
            for (i=0; i<dataList.size(); i++) {
                Map<String, Object> data = dataList.get(i);
                String typeId = (String) data.get("typeId");
                markService.deleteMark(taskId, Integer.parseInt(typeId));
//                markService.createMark(taskId, typeId, geoArr.get(i));
            }

        }else {
            int i=0;
            for (i=0; i<dataList.size(); i++) {
                Map<String, Object> data = dataList.get(i);
                String typeId = (String) data.get("typeId");
//                markService.createMark(taskId, typeId, geoArr.get(i));
                // 由于没有marktable，所有在这里无需更新
//                await TaskModal.updateTaskMarkTableById(id, markTableName);
            }
        }
        return ResultGenerator.getSuccessResult("mark创建成功");


    }
}
