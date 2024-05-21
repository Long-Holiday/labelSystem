package com.example.labelMark.controller;

import com.example.labelMark.domain.Mark;
import com.example.labelMark.service.MarkService;
import com.example.labelMark.service.TaskService;
import com.example.labelMark.utils.CoordinateConverter;
import com.example.labelMark.utils.ResultGenerator;
import com.example.labelMark.vo.constant.Result;
import com.fasterxml.jackson.core.JsonProcessingException;
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

    @Resource
    private TaskService taskService;

    @GetMapping("/saveMarkInfo")
    public Result saveMarkInfo(@RequestBody Map<String, Object> request){
        int taskId = (int) request.get("task_id");
        int userId = (int) request.get("user_id");
//        int typeId = (int) request.get("type_id");
        List<Map<String, Object>> geojsonArr = (List<Map<String, Object>>) request.get("jsondataArr");
        List<String> typeArr = (List<String>) request.get("typeArr");

        Mark mark = new Mark();

        List<Map<String, Object>> geometryArr = CoordinateConverter.convertCoordinate(geojsonArr);
        // 处理 markInfo
        List<Map<String, Object>> markInfoArr = CoordinateConverter.processMarkInfo(geometryArr, typeArr);


//        String[] typeArrStr = typeArr.split(",");
//        for(String typeId : typeArrStr){
//
//        }
//        for (Map<String, Object> data : dataList) {
//            String typeId = (String) data.get("typeId");
////            System.out.println("typeId: " + typeId);
//            // 过滤，检测typeArr中的typeId与geometryArr中的typeId信息是否相匹配
//            // 将typeId匹配成功的geomtryArr添加到geomArr中
//            List<String> geomArr = null;
//        }

        if(markInfoArr.isEmpty()){
            System.out.println("无标注信息");
            for (String ArrId : typeArr) {
//                String typeId = (String) data.get("typeId");
                markService.deleteMark(taskId, userId, Integer.parseInt(ArrId));
            }
            return ResultGenerator.getSuccessResult("没有标注信息，已删除多余Type");
        }

        boolean exist = markService.isMark(taskId, userId);
        if(exist){
            System.out.println("存在task为："+taskId+"的mark");
            for (String ArrId : typeArr) {
//                String typeId = (String) data.get("typeId");
                markService.deleteMark(taskId, userId, Integer.parseInt(ArrId));
            }
            for(Map<String, Object> geom : markInfoArr){
                mark.setTaskId(taskId);
                mark.setUserId(userId);
                mark.setGeom(geom.toString());
                markService.insertMark(mark);
            }
            return ResultGenerator.getSuccessResult("有标注信息，覆盖旧mark，建立新mark");
        }else {
            for(Map<String, Object> geom : markInfoArr){
                mark.setTaskId(taskId);
                mark.setUserId(userId);
                mark.setGeom(geom.toString());
                markService.insertMark(mark);
                taskService.updateTask(taskId, mark.getId());
            }
        }
        return ResultGenerator.getSuccessResult("mark创建成功");


    }
}
