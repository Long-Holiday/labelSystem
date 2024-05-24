package com.example.labelMark.mapper;

import com.example.labelMark.domain.TaskAccepted;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Delete;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Options;

/**
 * <p>
 *  Mapper 接口
 * </p>
 *
 * @author hjw
 * @since 2024-04-25
 */
@Mapper
public interface TaskAcceptedMapper extends BaseMapper<TaskAccepted> {

    @Delete("delete from task_accepted where task_id=#{id}")
    void deleteTaskAcceptByTaskId(int id);

//    @Options(useGeneratedKeys = true, keyProperty = "id", keyColumn = "id")
    TaskAccepted createTaskAccept(Integer taskId, String username, String typeArr);
}
