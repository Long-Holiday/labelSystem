package com.example.labelMark.controller;

import cn.hutool.core.util.StrUtil;
import com.example.labelMark.domain.Mark;
import com.example.labelMark.domain.Type;
import com.example.labelMark.service.MarkService;
import com.example.labelMark.service.TaskService;
import com.example.labelMark.utils.CoordinateConverter;
import com.example.labelMark.utils.ResultGenerator;
import com.example.labelMark.vo.constant.Result;
import com.fasterxml.jackson.core.JsonProcessingException;
import org.springframework.web.bind.annotation.*;

import javax.annotation.Resource;
import java.util.ArrayList;
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

    @PostMapping("/saveMarkInfo")
    public Result saveMarkInfo(@RequestBody Map<String, Object> request) {
        Integer userId = Integer.valueOf(request.get("userid").toString());
        int taskId = (Integer) request.get("id");
        List<Map<String, Object>> typeIdAndMarkInfoArr = (List<Map<String, Object>>) request.get("jsondataArr");
        List<Map<String, Object>> typeMapArr = (List<Map<String, Object>>) request.get("typeArr");
        List<Type> typeArr = new ArrayList<>();
        for (Map typeMap : typeMapArr) {
            Type type = new Type();
            Integer typeId = Integer.valueOf(typeMap.get("typeId").toString());
            String typeName = typeMap.get("typeName").toString();
            String typeColor = typeMap.get("typeColor").toString();
            type.setTypeColor(typeColor);
            type.setTypeName(typeName);
            type.setTypeId(typeId);
            typeArr.add(type);
        }

        List<Map<String, Object>> geometryArr = CoordinateConverter.convertCoordinate(typeIdAndMarkInfoArr);
        // 处理 markInfo
        List<Map<String, Object>> markInfoArr = CoordinateConverter.processMarkInfo(geometryArr, typeArr);


        if (markInfoArr.isEmpty()) {
            for (Type type : typeArr) {
//                String typeId = (String) data.get("typeId");
                markService.deleteMark(taskId, userId, type.getTypeId());
            }
            return ResultGenerator.getSuccessResult("没有标注信息，已删除多余Type");
        }

        boolean exist = markService.isMark(taskId, userId);
        if(exist) {
            for (Type type : typeArr) {
                markService.deleteMark(taskId, userId, type.getTypeId());
            }
//            清空任务表中已存在的任务标注
            taskService.updateTask(taskId, null);
            for (Map<String, Object> geomAndTypeId : markInfoArr) {
                Mark mark = new Mark();
                mark.setTaskId(taskId);
                mark.setUserId(userId);
                mark.setGeom(geomAndTypeId.get("geom").toString());
                mark.setStatus(0);
                mark.setTypeId(Integer.valueOf(geomAndTypeId.get("typeId").toString()));
                markService.insertMark(mark);
                String markIdStr = taskService.getMarkIdById(taskId);
                markIdStr = markIdStr == null ? mark.getId().toString()
                        : markIdStr + "," + mark.getId().toString();
                taskService.updateTask(taskId, markIdStr);
            }
            return ResultGenerator.getSuccessResult("有标注信息，覆盖旧mark，建立新mark");
        }else {
            for (Map<String, Object> geomAndTypeId : markInfoArr) {
                Mark mark = new Mark();
                mark.setTaskId(taskId);
                mark.setUserId(userId);
                mark.setGeom(geomAndTypeId.get("geom").toString());
                mark.setStatus(0);
                mark.setTypeId(Integer.valueOf(geomAndTypeId.get("typeId").toString()));
                markService.insertMark(mark);
                String markIdStr = taskService.getMarkIdById(taskId);
                markIdStr = markIdStr == null ? mark.getId().toString()
                        : markIdStr + "," + mark.getId().toString();
                taskService.updateTask(taskId, markIdStr);
            }
        }
        return ResultGenerator.getSuccessResult("mark创建成功");
    }
}
