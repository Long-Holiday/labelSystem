package com.example.labelMark.service;

import com.example.labelMark.domain.Mark;
import com.baomidou.mybatisplus.extension.service.IService;

import java.util.List;

/**
 * <p>
 *  服务类
 * </p>
 *
 * @author hjw
 * @since 2024-04-28
 */
public interface MarkService extends IService<Mark> {

    boolean isMark(int taskId);

    void createMark(int taskId, int typeId, String geom);

//    List<String> getMarkInfoArr()

    void deleteMarkByName(String markName);

    void deleteMark(int taskId, int typeId);


}
