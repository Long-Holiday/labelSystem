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

    boolean isMark(int taskId, int userId);

    void createMark(int taskId, int userId, int typeId, String geom);

    void deleteMark(int taskId, int userId, int typeId);

    void insertMark(Mark mark);

    List<Mark> getMarkByTaskId(Integer taskId);

    void deleteMarkByTaskId(int taskId);

    long GetTaskIdNum(int taskId);
}
